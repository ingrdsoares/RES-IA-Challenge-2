"""Explicit immutable generations; never rebuild a live collection at startup."""

from uuid import NAMESPACE_URL, uuid4, uuid5

from qdrant_client import models
from sqlalchemy import func, select, update

from app.assistant.agents.checkpoints import fingerprint
from app.legal.models import LegalIndexGeneration, NormVersion
from app.legal.schemas import LegalDocument
from app.sparse import vetor_documento


def catalog(db):
    versions = db.scalars(
        select(NormVersion).where(NormVersion.status == "ready").order_by(NormVersion.id)
    ).all()
    return versions, fingerprint(
        [
            {
                "id": str(v.id),
                "checksum": v.checksum,
                "metadata": v.metadata_hash,
                "anchors": v.anchors,
            }
            for v in versions
        ]
    )


def build_generation(db, index, storage, embed, dimensions):
    versions, digest = catalog(db)
    if not versions:
        raise ValueError("Catálogo vazio")
    collection = "legal_versions_hybrid_v1_" + uuid4().hex
    index.create_collection(
        collection,
        vectors_config={
            "dense": models.VectorParams(size=dimensions, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    expected = 0
    for version in versions:
        document = LegalDocument.model_validate_json(storage.get(version.json_key, private=False))
        if {s.anchor_id for s in document.sections} != set(version.anchors):
            raise ValueError("Âncoras divergem do catálogo")
        points = []
        for section in document.sections:
            vector = embed(section.text)
            if len(vector) != dimensions:
                raise ValueError("Dimensão incompatível")
            indices, values = vetor_documento(section.text)
            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"{version.id}/{section.anchor_id}")),
                    vector={
                        "dense": vector,
                        "sparse": models.SparseVector(indices=indices, values=values),
                    },
                    payload={
                        "document_id": str(version.document_id),
                        "version_id": str(version.id),
                        "anchor_id": section.anchor_id,
                        "text": section.text,
                        "title": version.title,
                        "jurisdiction": version.jurisdiction,
                        "effective_from_day": version.effective_from.toordinal()
                        if version.effective_from
                        else None,
                        "effective_to_day": version.effective_to.toordinal()
                        if version.effective_to
                        else None,
                    },
                )
            )
        index.upsert(collection, points, wait=True)
        expected += len(points)
    if index.count(collection, exact=True).count != expected:
        raise ValueError("Índice incompleto")
    generation = LegalIndexGeneration(
        collection=collection, catalog_hash=digest, points=expected, dimensions=dimensions
    )
    db.add(generation)
    db.flush()
    return generation


def activate_generation(db, index, generation_id):
    db.execute(select(func.pg_advisory_xact_lock(170011)))
    generation = db.get(LegalIndexGeneration, generation_id)
    if generation is None or generation.catalog_hash != catalog(db)[1]:
        raise ValueError("Geração desatualizada")
    config = index.get_collection(generation.collection).config.params
    if (
        not isinstance(config.vectors, dict)
        or config.vectors["dense"].size != generation.dimensions
        or "sparse" not in (config.sparse_vectors or {})
        or index.count(generation.collection, exact=True).count != generation.points
    ):
        raise ValueError("Geração incompatível ou incompleta")
    db.execute(
        update(LegalIndexGeneration)
        .where(LegalIndexGeneration.status == "active")
        .values(status="retired")
    )
    generation.status = "active"
    db.flush()


def active_collection(db):
    generation = db.scalar(
        select(LegalIndexGeneration).where(LegalIndexGeneration.status == "active")
    )
    if generation and generation.catalog_hash == catalog(db)[1]:
        return generation.collection
    return None
