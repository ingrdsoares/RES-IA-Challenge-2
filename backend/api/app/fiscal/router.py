from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.access.models import Account
from app.companies.service import require_company
from app.db import get_db
from app.dependencies import require_account
from app.fiscal.models import Calculation
from app.fiscal.schemas import CalculationInput
from app.fiscal.service import calculate
from app.serialization import record

router = APIRouter(tags=["Cálculos"])


@router.post("/empresas/{company_id}/calculos", status_code=201)
def create(
    company_id: UUID,
    data: CalculationInput,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    result = calculate(db, company_id, account.id, data)
    db.commit()
    return record(result)


@router.get("/calculos/{calculation_id}")
def get(
    calculation_id: UUID, account: Account = Depends(require_account), db: Session = Depends(get_db)
):
    result = db.get(Calculation, calculation_id)
    if not result:
        raise HTTPException(404, "Cálculo não encontrado")
    require_company(db, account.id, result.company_id)
    return record(result)
