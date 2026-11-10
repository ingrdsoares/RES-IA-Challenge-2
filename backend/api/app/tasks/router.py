from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.models import Account
from app.companies.service import require_company
from app.db import get_db
from app.dependencies import require_account
from app.pagination import page
from app.serialization import record
from app.tasks.models import Task, TaskEvent
from app.tasks.schemas import TaskInput, TaskPatch
from app.tasks.service import complete_task, create_task, require_task

router = APIRouter(tags=["Tarefas"])


@router.post("/empresas/{company_id}/tarefas", status_code=201)
def create(
    company_id: UUID,
    data: TaskInput,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    return record(create_task(db, company_id, account.id, data))


@router.get("/empresas/{company_id}/tarefas")
def tasks(
    company_id: UUID,
    completed: bool | None = None,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    require_company(db, account.id, company_id)
    query = select(Task).where(Task.company_id == company_id)
    if completed is not None:
        query = query.where(Task.completed == completed)
    return page(db, query, Task, record, limit, cursor)


@router.get("/tarefas/{task_id}")
def get(task_id: UUID, account: Account = Depends(require_account), db: Session = Depends(get_db)):
    return record(require_task(db, account.id, task_id))


@router.patch("/tarefas/{task_id}")
def patch(
    task_id: UUID,
    data: TaskPatch,
    idempotency_key: str = Header(..., min_length=1, max_length=128),
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    task = require_task(db, account.id, task_id, lock=True)
    return complete_task(db, task, account.id, data.completed, idempotency_key)


@router.get("/tarefas/{task_id}/historico")
def history(
    task_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    require_task(db, account.id, task_id)
    return page(
        db, select(TaskEvent).where(TaskEvent.task_id == task_id), TaskEvent, record, limit, cursor
    )
