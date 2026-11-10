from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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
    return {
        "operation_id": operation.id,
        "status": operation.status,
        "result": operation.result,
        "error": operation.error,
    }
