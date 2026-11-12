from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _agora() -> datetime:
    return datetime.now(UTC)


class ConsultaRag(Base):
    """Métrica por consulta. LGPD: sem pergunta, resposta, conta ou IP; só números e rótulos."""

    __tablename__ = "rag_consultas"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # X-Request-ID pode vir do cliente: não é único.
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, index=True
    )
    status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[int] = mapped_column(Integer)
    sources: Mapped[int] = mapped_column(Integer)
    collection: Mapped[str] = mapped_column(String(255))


class AvaliacaoRag(Base):
    """Avaliação útil/não útil de uma resposta; uma por conta e request id. Sem texto livre."""

    __tablename__ = "rag_avaliacoes"
    __table_args__ = (UniqueConstraint("request_id", "account_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    useful: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora)
