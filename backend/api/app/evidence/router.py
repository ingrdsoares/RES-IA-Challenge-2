from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.access.models import Account
from app.companies.service import require_company
from app.db import get_db
from app.dependencies import require_account
from app.evidence.models import Evidence, Obligation
from app.evidence.schemas import EvidenceInput, ObligationInput
from app.evidence.service import get_fiscal_status, record_evidence, require_evidence, store_file
from app.legal.ingest import storage_from_settings
from app.pagination import page
from app.serialization import record

router = APIRouter(tags=["Evidências"])


@router.post("/empresas/{company_id}/obrigacoes", status_code=201)
def create_obligation(
    company_id: UUID,
    data: ObligationInput,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    require_company(db, account.id, company_id)
    item = Obligation(company_id=company_id, **data.model_dump())
    db.add(item)
    db.commit()
    return record(item)


@router.get("/empresas/{company_id}/obrigacoes")
def obligations(
    company_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    require_company(db, account.id, company_id)
    return page(
        db,
        select(Obligation).where(Obligation.company_id == company_id),
        Obligation,
        record,
        limit,
        cursor,
    )


@router.post("/empresas/{company_id}/evidencias", status_code=201)
def create_evidence(
    company_id: UUID,
    data: EvidenceInput,
    idempotency_key: str = Header(..., min_length=1, max_length=128),
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    return record_evidence(db, company_id, account.id, data, idempotency_key)


@router.get("/empresas/{company_id}/evidencias")
def evidence(
    company_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    require_company(db, account.id, company_id)
    return page(
        db,
        select(Evidence).where(Evidence.company_id == company_id),
        Evidence,
        record,
        limit,
        cursor,
    )


@router.put("/evidencias/{evidence_id}/arquivo")
async def upload(
    evidence_id: UUID,
    request: Request,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    item = require_evidence(db, account.id, evidence_id, lock=True)
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > 10 * 1024 * 1024:
            raise HTTPException(413, "Arquivo excede 10 MiB")
        content.extend(chunk)
    return await run_in_threadpool(
        store_file,
        db,
        item,
        bytes(content),
        request.headers.get("content-type", ""),
        storage_from_settings(request.app.state.settings),
    )


@router.get("/evidencias/{evidence_id}/arquivo")
def download(
    evidence_id: UUID,
    request: Request,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    item = require_evidence(db, account.id, evidence_id)
    if not item.storage_key:
        raise HTTPException(404, "Anexo não disponível")
    return {
        "url": storage_from_settings(request.app.state.settings).signed_get(
            item.storage_key, private=True
        )
    }


@router.get("/empresas/{company_id}/situacao-fiscal")
def fiscal_status(
    company_id: UUID, account: Account = Depends(require_account), db: Session = Depends(get_db)
):
    require_company(db, account.id, company_id)
    return get_fiscal_status(db, company_id)
