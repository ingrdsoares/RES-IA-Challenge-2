import hashlib
from pathlib import Path
from uuid import UUID

import ollama
from fastapi import HTTPException
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
from app.db import session_factory
from app.jobs.service import enqueue
from app.legal.index import index_version
from app.legal.models import Norm, NormVersion
from app.legal.normalize import normalize
from app.legal.schemas import IngestMetadata, LegalDocument
from app.security import digest
from app.storage import ObjectStorage


def storage_from_settings(settings: Settings) -> ObjectStorage:
    return ObjectStorage(
        settings.s3_endpoint,
        settings.s3_public_endpoint,
        settings.s3_access_key,
        settings.s3_secret_key,
        allowed_origins=settings.allowed_origins,
    )


def ingest_file(
    path: Path, metadata: IngestMetadata, operation_key: str, *, db=None, storage=None
) -> UUID:
    if db is None:
        settings = Settings()
        factory = session_factory(settings.database_url)
        try:
            with factory.begin() as session:
                return ingest_file(
                    path,
                    metadata,
                    operation_key,
                    db=session,
                    storage=storage or storage_from_settings(settings),
                )
        finally:
            factory.kw["bind"].dispose()
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Documento excede 20 MiB")
    raw = path.read_bytes()
    media_type = {
        ".html": "text/html",
        ".htm": "text/html",
        ".md": "text/markdown",
        ".pdf": "application/pdf",
    }.get(path.suffix.lower())
    if media_type is None:
        raise ValueError("Formato não suportado")
    checksum = hashlib.sha256(raw).hexdigest()
    metadata_hash = digest(metadata.model_dump_json())
    db.execute(
        insert(Norm)
        .values(document_key=metadata.document_key)
        .on_conflict_do_nothing(index_elements=["document_key"])
    )
    # Serialize ingests for a document, including version label conflicts.
    norm = db.scalar(
        select(Norm).where(Norm.document_key == metadata.document_key).with_for_update()
    )
    version = db.scalar(
        select(NormVersion).where(
            NormVersion.document_id == norm.id, NormVersion.version_label == metadata.version_label
        )
    )
    if version:
        if version.checksum != checksum or version.metadata_hash != metadata_hash:
            raise HTTPException(409, "Versão imutável: use uma nova identificação de versão")
    else:
        version = NormVersion(
            document_id=norm.id,
            version_label=metadata.version_label,
            title=metadata.title,
            authority=metadata.authority,
            norm_type=metadata.norm_type,
            subjects=metadata.subjects,
            official_url=str(metadata.official_url),
            effective_from=metadata.effective_from,
            effective_to=metadata.effective_to,
            checksum=checksum,
            metadata_hash=metadata_hash,
            media_type=media_type,
            original_key="pending",
        )
        db.add(version)
        db.flush()
        version.original_key = f"{norm.id}/{version.id}/original{path.suffix.lower()}"
        storage.initialize()
        storage.put(version.original_key, raw, media_type, private=False)
    enqueue(db, "legal.ingest", None, None, operation_key, {"version_id": str(version.id)})
    return version.id


def publish_version(db, version_id: UUID):
    version = db.get(NormVersion, version_id)
    if (
        not version.json_key
        or not version.anchors
        or len(set(version.anchors)) != len(version.anchors)
    ):
        raise ValueError("Versão incompleta")
    version.status = "ready"
    db.flush()


def process_version(db, version, storage, index, embed, dimensions=1024):
    if version.status == "ready":
        return
    version.status = "processing"
    raw = storage.get(version.original_key, private=False)
    if hashlib.sha256(raw).hexdigest() != version.checksum:
        raise ValueError("Checksum do original diverge")
    document = normalize(raw, version.media_type)
    version.json_key = f"{version.document_id}/{version.id}/document.json"
    storage.put(
        version.json_key, document.model_dump_json().encode(), "application/json", private=False
    )
    saved = LegalDocument.model_validate_json(storage.get(version.json_key, private=False))
    index_version(index, version, saved, embed, dimensions)
    version.search_vector = func.to_tsvector(
        "simple", "\n".join(section.text for section in saved.sections)
    )
    version.anchors = [section.anchor_id for section in saved.sections]
    publish_version(db, version.id)


def handle_ingestion(db, operation):
    settings = Settings()
    version = db.get(NormVersion, UUID(operation.payload["version_id"]))
    storage = storage_from_settings(settings)
    index = QdrantClient(url=str(settings.qdrant_url), timeout=settings.qdrant_timeout)
    model = ollama.Client(host=str(settings.ollama_url), timeout=settings.ollama_timeout)
    try:

        def embed(text):
            return model.embed(
                model=settings.embedding_model, input=text, truncate=False
            ).embeddings[0]

        process_version(db, version, storage, index, embed, settings.embedding_dimensions)
        return {"version_id": str(version.id)}
    finally:
        index.close()
        model._client.close()
