from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access.models import Account
from app.companies.models import Company
from app.companies.schemas import CompanyInput, CompanyPatch, CompanyView
from app.companies.service import require_company
from app.db import get_db
from app.dependencies import require_account

router = APIRouter(prefix="/empresas", tags=["Empresas"])


def provenance(fields):
    return {
        key: {"origin": "declared", "updated_at": datetime.now(UTC).isoformat()} for key in fields
    }


@router.post("", response_model=CompanyView, status_code=201)
def create(
    data: CompanyInput, account: Account = Depends(require_account), db: Session = Depends(get_db)
):
    company = Company(
        owner_account_id=account.id,
        **data.model_dump(),
        provenance=provenance(type(data).model_fields),
    )
    db.add(company)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CNPJ já cadastrado nesta conta") from None
    return company


@router.get("")
def list_companies(
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
):
    query = select(Company).where(Company.owner_account_id == account.id)
    if cursor:
        try:
            date_text, id_text = cursor.split("|")
            after = datetime.fromisoformat(date_text)
            if after.tzinfo is None:
                raise ValueError("timezone required")
            query = query.where(
                tuple_(Company.created_at, Company.id) > tuple_(after, UUID(id_text))
            )
        except ValueError:
            raise HTTPException(422, "Cursor inválido") from None
    rows = list(db.scalars(query.order_by(Company.created_at, Company.id).limit(limit + 1)))
    page = rows[:limit]
    next_cursor = f"{page[-1].created_at.isoformat()}|{page[-1].id}" if len(rows) > limit else None
    return {"items": [CompanyView.model_validate(row) for row in page], "next_cursor": next_cursor}


@router.get("/{company_id}", response_model=CompanyView)
def get(
    company_id: UUID, account: Account = Depends(require_account), db: Session = Depends(get_db)
):
    return require_company(db, account.id, company_id)


@router.patch("/{company_id}", response_model=CompanyView)
def patch(
    company_id: UUID,
    data: CompanyPatch,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    company = require_company(db, account.id, company_id)
    changes = data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Campos não podem ser nulos")
    for name, value in changes.items():
        setattr(company, name, value)
    company.provenance = {**company.provenance, **provenance(changes)}
    db.commit()
    return company
