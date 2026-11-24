from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("owner_account_id", "cnpj"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    cnpj: Mapped[str] = mapped_column(String(14))
    cnae: Mapped[str] = mapped_column(String(7))
    size: Mapped[str] = mapped_column(String(30))
    regime: Mapped[str] = mapped_column(String(40))
    municipality: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(2))
    provenance: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CompanyRevenue(Base):
    __tablename__ = "company_revenues"
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CompanyMonthlyRevenue(Base):
    __tablename__ = "company_monthly_revenues"
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    period: Mapped[str] = mapped_column(String(7), primary_key=True)
    trade_without_invoice: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    trade_with_invoice: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    industry_without_invoice: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    industry_with_invoice: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    services_without_invoice: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    services_with_invoice: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @hybrid_property
    def total(self):
        return (
            self.trade_without_invoice
            + self.trade_with_invoice
            + self.industry_without_invoice
            + self.industry_with_invoice
            + self.services_without_invoice
            + self.services_with_invoice
        )
