"""Lembretes de vencimento: no máximo um e-mail por conta e por dia, só para quem ativou.

A mensagem leva apenas datas e quantidades. O cadastro não confirma o e-mail, então nenhum texto
escrito pelo usuário pode ser enviado por aqui.
"""

from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import mail
from app.access.models import Account
from app.companies.models import Company
from app.config import Settings
from app.evidence.models import Obligation
from app.jobs.models import Operation
from app.jobs.service import enqueue
from app.tasks.models import Task

KIND = "reminder.send"
DAYS_BEFORE = (0, 1, 7)
BRASILIA = timezone(timedelta(hours=-3))
FIRST_HOUR, LAST_HOUR = 8, 20


def today() -> date:
    return datetime.now(BRASILIA).date()


def due_counts(db: Session, day: date, account_id: UUID | None = None) -> dict[UUID, Counter]:
    """Pendências por conta e vencimento, entre as contas com lembrete ativo."""
    dates = [day + timedelta(days=days) for days in DAYS_BEFORE]
    counts: dict[UUID, Counter] = {}
    for model in (Task, Obligation):
        query = (
            select(Account.id, model.due_date)
            .join(Company, Company.owner_account_id == Account.id)
            .join(model, model.company_id == Company.id)
            .where(Account.reminders_enabled, model.due_date.in_(dates), model.completed.is_(False))
        )
        if account_id:
            query = query.where(Account.id == account_id)
        for owner, due in db.execute(query):
            counts.setdefault(owner, Counter())[due] += 1
    return counts


def schedule(db: Session, settings: Settings, now: datetime | None = None) -> int:
    local = (now or datetime.now(UTC)).astimezone(BRASILIA)
    if not settings.smtp_host or not settings.smtp_from:
        return 0
    if not FIRST_HOUR <= local.hour <= LAST_HOUR:
        return 0
    key = local.date().isoformat()
    queued = 0
    for account_id in due_counts(db, local.date()):
        existing = db.scalar(
            select(Operation).where(
                Operation.scope == str(account_id), Operation.kind == KIND, Operation.key == key
            )
        )
        if existing is None:
            enqueue(db, KIND, account_id, None, key, {"date": key})
        elif existing.status == "failed":
            existing.status, existing.attempts = "queued", 0
        else:
            continue
        queued += 1
    return queued


def send(db: Session, operation: Operation) -> dict:
    day = date.fromisoformat(operation.payload["date"])
    counts = due_counts(db, day, operation.owner_id).get(operation.owner_id)
    if day != today() or not counts:
        return {"sent": False}
    settings = Settings()
    lines = "\n".join(
        f"- {due:%d/%m/%Y}: {total} {'item' if total == 1 else 'itens'}"
        for due, total in sorted(counts.items())
    )
    mail.deliver(
        settings,
        db.get(Account, operation.owner_id).email,
        "Vencimentos próximos no Sócio Digital",
        f"Você tem pendências com vencimento próximo:\n\n{lines}\n\n"
        f"Veja os detalhes em {settings.frontend_url}#tarefas\n\n"
        "Para parar de receber, desative os lembretes na tela Tarefas e obrigações.",
    )
    return {"sent": True}
