from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.access.models import Account
from app.companies.models import CompanyMonthlyRevenue, CompanyRevenue
from app.companies.service import require_company
from app.db import get_db
from app.dependencies import require_account

router = APIRouter(prefix="/empresas/{company_id}", tags=["Faturamento"])

PERIOD = r"^(20[0-9]{2}|2100)-(0[1-9]|1[0-2])$"
Year = Annotated[int, Path(ge=2000, le=2100)]
Period = Annotated[str, Path(pattern=PERIOD)]


def _no_float(value):
    if isinstance(value, (float, bool)):
        raise ValueError("Use strings decimais para valores monetários")
    return value


Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]


class RevenueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Amount

    _strings = field_validator("*", mode="before")(_no_float)


class RevenueView(BaseModel):
    year: int
    amount: Decimal | None = None
    updated_at: datetime | None = None
    source: str | None = None


class MonthlyRevenueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trade_without_invoice: Amount
    trade_with_invoice: Amount
    industry_without_invoice: Amount
    industry_with_invoice: Amount
    services_without_invoice: Amount
    services_with_invoice: Amount

    _strings = field_validator("*", mode="before")(_no_float)


class MonthlyRevenueView(MonthlyRevenueInput):
    model_config = ConfigDict(from_attributes=True)
    period: str
    total: Decimal
    updated_at: datetime


class MonthlyRevenueList(BaseModel):
    items: list[MonthlyRevenueView]


def owned(
    company_id: UUID, account: Account = Depends(require_account), db: Session = Depends(get_db)
) -> UUID:
    return require_company(db, account.id, company_id).id


Owned = Annotated[UUID, Depends(owned)]


def annual_view(db: Session, company_id: UUID, year: int) -> RevenueView:
    total, updated_at = db.execute(
        select(
            func.sum(CompanyMonthlyRevenue.total), func.max(CompanyMonthlyRevenue.updated_at)
        ).where(
            CompanyMonthlyRevenue.company_id == company_id,
            CompanyMonthlyRevenue.period.startswith(f"{year}-"),
        )
    ).one()
    if total is not None:
        return RevenueView(year=year, amount=total, updated_at=updated_at, source="monthly")
    declared = db.get(CompanyRevenue, (company_id, year))
    if declared is None:
        return RevenueView(year=year)
    return RevenueView(
        year=year, amount=declared.amount, updated_at=declared.updated_at, source="annual"
    )


@router.get("/faturamento/{year}", response_model=RevenueView)
def get_revenue(company_id: Owned, year: Year, db: Session = Depends(get_db)):
    return annual_view(db, company_id, year)


@router.put("/faturamento/{year}", response_model=RevenueView)
def put_revenue(company_id: Owned, year: Year, data: RevenueInput, db: Session = Depends(get_db)):
    if annual_view(db, company_id, year).source == "monthly":
        raise HTTPException(409, "Este ano já tem meses lançados: ajuste o faturamento mensal")
    values = {"amount": data.amount, "updated_at": datetime.now(UTC)}
    db.execute(
        insert(CompanyRevenue)
        .values(company_id=company_id, year=year, **values)
        .on_conflict_do_update(index_elements=["company_id", "year"], set_=values)
    )
    db.commit()
    return annual_view(db, company_id, year)


@router.get("/faturamento-mensal", response_model=MonthlyRevenueList)
def list_months(
    company_id: Owned,
    start: Annotated[str, Query(alias="from", pattern=PERIOD)],
    end: Annotated[str, Query(alias="to", pattern=PERIOD)],
    db: Session = Depends(get_db),
):
    if end < start or int(end[:4]) - int(start[:4]) > 2:
        raise HTTPException(422, "Intervalo inválido")
    rows = db.scalars(
        select(CompanyMonthlyRevenue)
        .where(
            CompanyMonthlyRevenue.company_id == company_id,
            CompanyMonthlyRevenue.period.between(start, end),
        )
        .order_by(CompanyMonthlyRevenue.period)
    )
    return {"items": list(rows)}


@router.put("/faturamento-mensal/{period}", response_model=MonthlyRevenueView)
def put_month(
    company_id: Owned, period: Period, data: MonthlyRevenueInput, db: Session = Depends(get_db)
):
    values = {**data.model_dump(), "updated_at": datetime.now(UTC)}
    db.execute(
        insert(CompanyMonthlyRevenue)
        .values(company_id=company_id, period=period, **values)
        .on_conflict_do_update(index_elements=["company_id", "period"], set_=values)
    )
    db.commit()
    return db.get(CompanyMonthlyRevenue, (company_id, period))


@router.delete("/faturamento-mensal/{period}", status_code=204)
def delete_month(company_id: Owned, period: Period, db: Session = Depends(get_db)):
    removed = db.execute(
        delete(CompanyMonthlyRevenue).where(
            CompanyMonthlyRevenue.company_id == company_id,
            CompanyMonthlyRevenue.period == period,
        )
    ).rowcount
    if not removed:
        raise HTTPException(404, "Mês não lançado")
    db.commit()
    return Response(status_code=204)
