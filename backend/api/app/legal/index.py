from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.legal.models import NormVersion
from app.legal.schemas import LegalDocument

COLLECTION = "legal_versions_v1"


def index_version(
    client: QdrantClient,
    version: NormVersion,
    document: LegalDocument,
    embed,
    dimensions: int,
    collection: str = COLLECTION,
):
    if not client.collection_exists(collection):
        client.create_collection(
            collection,
            vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
        )
    config = client.get_collection(collection).config.params.vectors
    if (
        not isinstance(config, models.VectorParams)
        or config.size != dimensions
        or config.distance != models.Distance.COSINE
    ):
        raise ValueError("Índice jurídico incompatível; coleção preservada")
    points = []
    for section in document.sections:
        vector = embed(section.text)
        if len(vector) != dimensions:
            raise ValueError("Dimensão de embedding incompatível")
        points.append(
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, f"{version.id}/{section.anchor_id}")),
                vector=vector,
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
                    "effective_from": version.effective_from.isoformat()
                    if version.effective_from
                    else None,
                    "effective_to": version.effective_to.isoformat()
                    if version.effective_to
                    else None,
                },
            )
        )
    client.upsert(collection, points=points, wait=True)
