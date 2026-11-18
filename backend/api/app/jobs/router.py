from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.models import Account
from app.db import get_db
from app.dependencies import require_account
from app.jobs.models import Operation

router = APIRouter(tags=["Operações"])


@router.get("/operacoes/{operation_id}")
def get_operation(
    operation_id: UUID, account: Account = Depends(require_account), db: Session = Depends(get_db)
):
    operation = db.get(Operation, operation_id)
    if operation is None or operation.owner_id != account.id:
        raise HTTPException(404, "Operação não encontrada")
    from app.assistant.agents.models import AgentRun, AgentStep

    run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation.id))
    summary = None
    if run:
        stages = db.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run.id)
            .order_by(AgentStep.created_at, AgentStep.id)
        ).all()
        summary = {
            "run_id": run.id,
            "trace_id": run.trace_id,
            "status": run.status,
            "revision": run.revision,
            "calls": run.calls,
            "stages": [
                {
                    "name": step.name,
                    "revision": step.revision,
                    "status": step.status,
                    "attempts": step.attempts,
                    "model": step.model,
                    "prompt_version": step.prompt_version,
                    "usage": step.usage,
                    "error": step.error,
                }
                for step in stages
            ],
        }
    return {
        "run": summary,
        "operation_id": operation.id,
        "status": operation.status,
        "result": operation.result,
        "error": operation.error,
    }
