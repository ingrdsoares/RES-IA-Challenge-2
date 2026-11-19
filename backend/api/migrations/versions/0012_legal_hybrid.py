"""Administrative publication of immutable hybrid index generations."""

import sqlalchemy as sa
from alembic import op

revision = "0012_legal_hybrid"
down_revision = "0011_agent_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legal_index_generations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("collection", sa.String(120), nullable=False, unique=True),
        sa.Column("catalog_hash", sa.String(64), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_legal_active_generation",
        "legal_index_generations",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade():
    op.drop_table("legal_index_generations")
