from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Norm(Base):
    __tablename__ = "norms"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_key: Mapped[str] = mapped_column(String(256), unique=True)


class NormVersion(Base):
    __tablename__ = "norm_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_label"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("norms.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256))
    authority: Mapped[str] = mapped_column(String(256))
    jurisdiction: Mapped[str | None] = mapped_column(String(5))
    norm_type: Mapped[str] = mapped_column(String(256))
    subjects: Mapped[list] = mapped_column(JSON)
    official_url: Mapped[str] = mapped_column(String(2048))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    checksum: Mapped[str] = mapped_column(String(64))
    metadata_hash: Mapped[str] = mapped_column(String(64))
    original_key: Mapped[str] = mapped_column(String(512))
    json_key: Mapped[str | None] = mapped_column(String(512))
    anchors: Mapped[list] = mapped_column(JSON, default=list)
    media_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="received")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
