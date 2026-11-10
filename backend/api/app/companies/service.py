from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.companies.models import Company
from app.companies.schemas import CompanySnapshot


def require_company(db: Session, account_id: UUID, company_id: UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None or company.owner_account_id != account_id:
        raise HTTPException(404, "Empresa não encontrada")
    return company


def snapshot(company: Company) -> CompanySnapshot:
    return CompanySnapshot.model_validate(company)
