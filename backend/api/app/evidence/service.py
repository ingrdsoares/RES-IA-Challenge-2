import hashlib
from datetime import date

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from sqlalchemy import select

from app.companies.service import require_company
from app.evidence.models import Evidence, Obligation
from app.jobs.service import enqueue
from app.serialization import record

GUIDE_IMAGE_SIGNATURES = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}
PDF_MEDIA_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"
# Evidence kinds the assistant reads: guide images (vision) and DASN-SIMEI PDFs (local parser).
ASSISTANT_DOCUMENT_KINDS = ("guide", "declaration")


def assistant_document_supported(kind: str, media_type: str | None, vision: bool) -> bool:
    if kind == "declaration":
        return media_type == PDF_MEDIA_TYPE
    return vision and media_type in GUIDE_IMAGE_SIGNATURES


def require_evidence(db, account_id, evidence_id, lock=False):
    query = select(Evidence).where(Evidence.id == evidence_id)
    if lock:
        query = query.with_for_update()
    evidence = db.scalar(query)
    if not evidence:
        raise HTTPException(404, "Evidência não encontrada")
    require_company(db, account_id, evidence.company_id)
    return evidence


def obligation_record(obligation):
    return {**record(obligation), "completed": obligation.completed}


def require_obligation(db, account_id, obligation_id):
    obligation = db.scalar(
        select(Obligation).where(Obligation.id == obligation_id).with_for_update()
    )
    if not obligation:
        raise HTTPException(404, "Obrigação não encontrada")
    require_company(db, account_id, obligation.company_id)
    return obligation


def edit_obligation(db, obligation, data):
    if data.period and db.scalar(
        select(Evidence.id)
        .where(
            Evidence.obligation_id == obligation.id,
            Evidence.period.is_not(None),
            Evidence.period != data.period,
        )
        .limit(1)
    ):
        raise HTTPException(409, "Há evidência vinculada com outra competência")
    for name, value in data.model_dump().items():
        setattr(obligation, name, value)
    db.commit()
    return obligation


def delete_obligation(db, obligation):
    if db.scalar(select(Evidence.id).where(Evidence.obligation_id == obligation.id).limit(1)):
        raise HTTPException(409, "Há evidência vinculada a esta obrigação")
    db.delete(obligation)
    db.commit()


def require_guide_attachment(db, account_id, company_id, evidence_id) -> Evidence:
    evidence = require_evidence(db, account_id, evidence_id)
    if (
        evidence.company_id != company_id
        or evidence.kind not in ASSISTANT_DOCUMENT_KINDS
        or not evidence.storage_key
    ):
        raise HTTPException(404, "Documento não encontrado")
    return evidence


def guide_attachment_media_type(storage, key: str) -> str | None:
    try:
        return storage.content_type(key, private=True)
    except (BotoCoreError, ClientError):
        raise HTTPException(503, "Armazenamento indisponível") from None


def record_evidence(db, company_id, account_id, data, key):
    require_company(db, account_id, company_id)
    if data.obligation_id:
        obligation = db.get(Obligation, data.obligation_id)
        if not obligation or obligation.company_id != company_id:
            raise HTTPException(404, "Obrigação não encontrada")
        if data.period and obligation.period and data.period != obligation.period:
            raise HTTPException(422, "Competência diverge da obrigação vinculada")
    operation = enqueue(
        db, "evidence.record", account_id, company_id, key, data.model_dump(mode="json")
    )
    if operation.status == "succeeded":
        return operation.result
    evidence = Evidence(company_id=company_id, **data.model_dump())
    db.add(evidence)
    db.flush()
    operation.status = "succeeded"
    operation.result = record(evidence)
    db.commit()
    return operation.result


def store_file(db, evidence, content, content_type, storage):
    signatures = {
        PDF_MEDIA_TYPE: PDF_SIGNATURE,
        **GUIDE_IMAGE_SIGNATURES,
    }
    if content_type not in signatures or not content.startswith(signatures[content_type]):
        raise HTTPException(422, "Tipo ou assinatura do arquivo inválidos")
    checksum = hashlib.sha256(content).hexdigest()
    if evidence.storage_key:
        if evidence.checksum != checksum:
            raise HTTPException(409, "Anexo imutável: cadastre outra evidência")
        return record(evidence)
    key = f"{evidence.company_id}/{evidence.id}/{checksum}"
    try:
        storage.initialize()
        storage.put(key, content, content_type, private=True)
    except (BotoCoreError, ClientError):
        raise HTTPException(503, "Armazenamento indisponível") from None
    evidence.storage_key, evidence.checksum = key, checksum
    db.commit()
    return record(evidence)


def get_fiscal_status(db, company_id, period=None):
    indicators = {}
    for scope in ("registration", "federal_certificate", "obligations"):
        query = select(Evidence).where(Evidence.company_id == company_id, Evidence.scope == scope)
        if period and scope == "obligations":
            query = query.where(Evidence.period == period)
        evidence = db.scalar(
            query.order_by(Evidence.created_at.desc(), Evidence.id.desc()).limit(1)
        )
        indicators[scope] = {
            "verification": "unverified",
            "evidence_state": "absent"
            if evidence is None
            else "expired"
            if evidence.valid_until and evidence.valid_until < date.today()
            else "declared",
            "latest_evidence": record(evidence) if evidence else None,
        }
    return {"coverage": "partial", **indicators}
