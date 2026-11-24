from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.models import Account
from app.assistant.models import Message
from app.db import get_db
from app.dependencies import require_account
from app.jobs.models import Operation
from app.rate_limit import RateLimiter
from app.telemetria import service
from app.telemetria.models import AvaliacaoRag, ConsultaRag

router = APIRouter(prefix="/rag", tags=["Telemetria RAG"])

Motivo = Literal["incorreta", "incompleta", "desatualizada", "sem_fonte", "confusa", "outro"]


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=64)
    useful: bool
    reason: Motivo | None = None


def _resposta_do_assistente(db: Session, account_id: UUID, request_id: str) -> str | None:
    """Id da operação, se for uma resposta do assistente dada a esta conta."""
    try:
        operation_id = UUID(request_id)
    except ValueError:
        return None
    existe = db.scalar(
        select(Message.id)
        .join(Operation, Operation.id == Message.operation_id)
        .where(
            Operation.id == operation_id,
            Operation.owner_id == account_id,
            Message.role == "assistant",
        )
    )
    return str(operation_id) if existe else None


@router.post("/feedback", status_code=204, dependencies=[Depends(RateLimiter())])
def feedback(
    payload: FeedbackIn,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    request_id = payload.request_id
    consulta = db.scalar(
        select(ConsultaRag.id).where(ConsultaRag.request_id == request_id).limit(1)
    )
    if consulta is None:
        request_id = _resposta_do_assistente(db, account.id, request_id)
        if request_id is None:
            raise HTTPException(404, "Consulta não encontrada")
    atual = db.scalar(
        select(AvaliacaoRag).where(
            AvaliacaoRag.request_id == request_id, AvaliacaoRag.account_id == account.id
        )
    )
    # Motivo só faz sentido para "não útil".
    reason = None if payload.useful else payload.reason
    if atual:
        atual.useful, atual.reason = payload.useful, reason
    else:
        db.add(
            AvaliacaoRag(
                request_id=request_id,
                account_id=account.id,
                useful=payload.useful,
                reason=reason,
            )
        )
    db.commit()


@router.get("/metricas", dependencies=[Depends(service.require_admin), Depends(RateLimiter())])
def metricas(
    inicio: date = Query(alias="from"),
    fim: date = Query(alias="to"),
    db: Session = Depends(get_db),
):
    if fim < inicio or (fim - inicio).days > 92:
        raise HTTPException(422, "Intervalo inválido (máximo de 93 dias)")
    return {"from": inicio, "to": fim, "days": service.agregados(db, inicio, fim)}
