"""Métricas por consulta RAG (sem conteúdo) e avaliações de resposta."""

import sqlalchemy as sa
from alembic import op

revision = "0010_telemetria_rag"
down_revision = "0009_norm_jurisdiction"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rag_consultas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("sources", sa.Integer(), nullable=False),
        sa.Column("collection", sa.String(255), nullable=False),
    )
    op.create_index("ix_rag_consultas_request_id", "rag_consultas", ["request_id"])
    op.create_index("ix_rag_consultas_created_at", "rag_consultas", ["created_at"])
    op.create_table(
        "rag_avaliacoes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("useful", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "account_id"),
    )
    op.create_index("ix_rag_avaliacoes_request_id", "rag_avaliacoes", ["request_id"])


def downgrade():
    op.drop_table("rag_avaliacoes")
    op.drop_table("rag_consultas")
