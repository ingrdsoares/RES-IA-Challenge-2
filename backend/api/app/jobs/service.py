import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.jobs.models import Operation
from app.security import digest


def enqueue(
    db: Session, kind: str, owner_id: UUID | None, company_id: UUID | None, key: str, payload: dict
) -> Operation:
    if not key or len(key) > 128:
        raise HTTPException(422, "Chave de idempotência inválida")
    scope = str(company_id or owner_id or "admin")
    fingerprint = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    query = select(Operation).where(
        Operation.scope == scope, Operation.kind == kind, Operation.key == key
    )
    operation = db.scalar(query)
    if operation is None:
        try:
            with db.begin_nested():
                operation = Operation(
                    owner_id=owner_id,
                    company_id=company_id,
                    scope=scope,
                    kind=kind,
                    key=key,
                    payload=payload,
                    payload_hash=fingerprint,
                )
                db.add(operation)
                db.flush()
        except IntegrityError:
            operation = db.scalar(query)
            if operation is None:
                raise
    if operation.payload_hash != fingerprint or operation.owner_id != owner_id:
        raise HTTPException(409, "Chave já usada para outra operação")
    return operation
