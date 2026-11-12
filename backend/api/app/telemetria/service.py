import logging
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.models import Account
from app.dependencies import require_account
from app.telemetria.models import ConsultaRag

logger = logging.getLogger(__name__)


def registrar(
    db_factory, request_id: str, status: str, latency_ms: int, sources: int, collection: str
) -> None:
    """Grava a métrica; falha de telemetria nunca derruba a consulta."""
    try:
        with db_factory() as db:
            db.add(
                ConsultaRag(
                    request_id=request_id[:64],
                    status=status,
                    latency_ms=latency_ms,
                    sources=sources,
                    collection=collection,
                )
            )
            db.commit()
    except Exception:
        logger.warning("Falha ao registrar telemetria da consulta", exc_info=True)


def require_admin(request: Request, account: Account = Depends(require_account)) -> Account:
    # ponytail: sem papéis no modelo Account; lista de e-mails em ADMIN_EMAILS (separada por
    # vírgula). Migrar para coluna de papel se houver mais de um perfil administrativo.
    lista = request.app.state.settings.admin_emails
    admins = {e.strip().lower() for e in lista.split(",") if e.strip()}
    if account.email.lower() not in admins:
        raise HTTPException(403, "Acesso restrito a administradores")
    return account


def _p95(values: list[int]) -> int:
    if len(values) < 2:
        return values[0]
    return round(statistics.quantiles(values, n=20, method="inclusive")[-1])


def agregados(db: Session, inicio: date, fim: date) -> list[dict]:
    """Contagem por status/dia (UTC) e latência mediana/p95; `fim` inclusivo."""
    de = datetime.combine(inicio, time.min, UTC)
    ate = datetime.combine(fim + timedelta(days=1), time.min, UTC)
    linhas = db.execute(
        select(ConsultaRag.created_at, ConsultaRag.status, ConsultaRag.latency_ms).where(
            ConsultaRag.created_at >= de, ConsultaRag.created_at < ate
        )
    )
    # ponytail: agrega em Python (portável, intervalo curto); percentile_cont no SQL se crescer.
    dias: dict[str, dict] = defaultdict(lambda: {"status": defaultdict(int), "lat": []})
    for criado, status, ms in linhas:
        dia = dias[criado.date().isoformat()]
        dia["status"][status] += 1
        dia["lat"].append(ms)
    return [
        {
            "date": d,
            "total": len(v["lat"]),
            "by_status": dict(v["status"]),
            "latency_ms_median": round(statistics.median(v["lat"])),
            "latency_ms_p95": _p95(v["lat"]),
        }
        for d, v in sorted(dias.items())
    ]
