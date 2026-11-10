from datetime import date
from uuid import UUID

from botocore.exceptions import ClientError
from fastapi import HTTPException
from sqlalchemy import select

from app.legal.models import NormVersion


def metadata(version):
    return {
        "document_id": version.document_id,
        "version_id": version.id,
        "title": version.title,
        "version_label": version.version_label,
        "authority": version.authority,
        "norm_type": version.norm_type,
        "subjects": version.subjects,
        "official_url": version.official_url,
        "effective_from": version.effective_from,
        "effective_to": version.effective_to,
    }


def object_available(storage, key):
    if not key:
        return False
    try:
        storage.client.head_object(Bucket="legal", Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise HTTPException(503, "Armazenamento temporariamente indisponível") from None


def resolve_citation(db, document_id: UUID, version_id: UUID, anchor_id: str | None, storage):
    version = db.get(NormVersion, version_id)
    if version is None or version.document_id != document_id or version.status != "ready":
        reference = db.scalar(
            select(NormVersion)
            .where(NormVersion.document_id == document_id, NormVersion.status == "ready")
            .order_by(NormVersion.created_at.desc())
            .limit(1)
        )
        if reference is None:
            raise HTTPException(404, "Norma não encontrada")
        return {
            "document_id": document_id,
            "version_id": version_id,
            "state": "version_unavailable",
            "official_url": reference.official_url,
            "json_url": None,
            "original_url": None,
            "anchor_id": None,
        }
    has_json = object_available(storage, version.json_key)
    has_original = object_available(storage, version.original_key)
    exact = anchor_id is None or (has_json and anchor_id in version.anchors)
    state = "exact" if exact and (has_json or has_original) else "anchor_unavailable"
    if not has_json and not has_original:
        state = "version_unavailable"
    return {
        **metadata(version),
        "state": state,
        "anchor_id": anchor_id if exact and has_json else None,
        "json_url": storage.signed_get(version.json_key, False) if has_json else None,
        "original_url": storage.signed_get(version.original_key, False) if has_original else None,
        "historical": bool(version.effective_to and version.effective_to < date.today()),
    }
