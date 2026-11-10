from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FiscalRule(Base):
    __tablename__ = "fiscal_rules"
    __table_args__ = (UniqueConstraint("kind", "version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    version: Mapped[str] = mapped_column(String(120))
    valid_from: Mapped[str] = mapped_column(String(7))
    valid_to: Mapped[str] = mapped_column(String(7))
    parameters: Mapped[dict] = mapped_column(JSON)
    references: Mapped[list] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_evidence: Mapped[str | None] = mapped_column(String(512))


class Calculation(Base):
    __tablename__ = "calculations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    rule_id: Mapped[UUID | None] = mapped_column(ForeignKey("fiscal_rules.id"))
    status: Mapped[str] = mapped_column(String(30))
    request: Mapped[dict] = mapped_column(JSON)
    company_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(256))
    references: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
