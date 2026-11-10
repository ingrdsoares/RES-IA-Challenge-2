import hashlib
from datetime import date

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from sqlalchemy import select

from app.companies.service import require_company
from app.evidence.models import Evidence, Obligation
from app.jobs.service import enqueue
from app.serialization import record


def require_evidence(db, account_id, evidence_id, lock=False):
    query = select(Evidence).where(Evidence.id == evidence_id)
    if lock:
        query = query.with_for_update()
    evidence = db.scalar(query)
    if not evidence:
        raise HTTPException(404, "Evidência não encontrada")
    require_company(db, account_id, evidence.company_id)
    return evidence


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
        "application/pdf": b"%PDF-",
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/jpeg": b"\xff\xd8\xff",
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
