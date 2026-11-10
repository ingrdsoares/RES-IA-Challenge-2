"""Company profiles owned by one account."""

import sqlalchemy as sa
from alembic import op

revision = "0002_companies"
down_revision = "0001_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("cnae", sa.String(7), nullable=False),
        sa.Column("size", sa.String(30), nullable=False),
        sa.Column("regime", sa.String(40), nullable=False),
        sa.Column("municipality", sa.String(120), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_account_id", "cnpj"),
    )
    op.create_index("ix_companies_owner_account_id", "companies", ["owner_account_id"])


def downgrade():
    op.drop_table("companies")
