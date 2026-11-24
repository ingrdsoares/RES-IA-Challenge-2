"""Receita bruta mensal, nos campos do relatório do MEI (Resolução CGSN 140, Anexo X)."""

import sqlalchemy as sa
from alembic import op

revision = "0017_monthly_revenue"
down_revision = "0016_archive_conversation"
branch_labels = None
depends_on = None

AMOUNTS = (
    "trade_without_invoice",
    "trade_with_invoice",
    "industry_without_invoice",
    "industry_with_invoice",
    "services_without_invoice",
    "services_with_invoice",
)


def upgrade():
    op.create_table(
        "company_monthly_revenues",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("period", sa.String(7), primary_key=True),
        *(sa.Column(name, sa.Numeric(18, 2), nullable=False) for name in AMOUNTS),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("company_monthly_revenues")
