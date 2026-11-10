from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import cast, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_account
from app.legal.ingest import storage_from_settings
from app.legal.models import Norm, NormVersion
from app.legal.service import metadata, resolve_citation

router = APIRouter(tags=["Biblioteca"], dependencies=[Depends(require_account)])


@router.get("/normas")
def list_norms(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=256),
    subject: str | None = None,
    norm_type: str | None = None,
    authority: str | None = None,
    effective_on: date | None = None,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
):
    query = select(NormVersion).join(Norm).where(NormVersion.status == "ready")
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                NormVersion.title.ilike(pattern, escape="\\"),
                Norm.document_key.ilike(pattern, escape="\\"),
                NormVersion.search_vector.op("@@")(func.plainto_tsquery("simple", q)),
            )
        )
    if subject:
        query = query.where(cast(NormVersion.subjects, JSONB).contains([subject]))
    if norm_type:
        query = query.where(NormVersion.norm_type == norm_type)
    if authority:
        query = query.where(NormVersion.authority == authority)
    if effective_on:
        query = query.where(
            NormVersion.effective_from <= effective_on,
            or_(NormVersion.effective_to.is_(None), NormVersion.effective_to >= effective_on),
        )
    if cursor:
        try:
            value, identifier = cursor.split("|")
            after = datetime.fromisoformat(value)
            if after.tzinfo is None:
                raise ValueError("timezone required")
            query = query.where(
                tuple_(NormVersion.created_at, NormVersion.id) > tuple_(after, UUID(identifier))
            )
        except ValueError:
            raise HTTPException(422, "Cursor inválido") from None
    rows = list(db.scalars(query.order_by(NormVersion.created_at, NormVersion.id).limit(limit + 1)))
    page = rows[:limit]
    return {
        "items": [metadata(row) for row in page],
        "next_cursor": f"{page[-1].created_at.isoformat()}|{page[-1].id}"
        if len(rows) > limit
        else None,
    }


@router.get("/normas/{document_id}/versoes/{version_id}")
def reader(document_id: UUID, version_id: UUID, request: Request, db: Session = Depends(get_db)):
    return resolve_citation(
        db, document_id, version_id, None, storage_from_settings(request.app.state.settings)
    )


@router.get("/citacoes/resolver")
def citation(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    anchor_id: str | None = Query(None, max_length=256),
    db: Session = Depends(get_db),
):
    return resolve_citation(
        db, document_id, version_id, anchor_id, storage_from_settings(request.app.state.settings)
    )
