from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
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
