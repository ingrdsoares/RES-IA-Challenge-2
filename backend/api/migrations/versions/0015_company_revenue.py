"""Receita bruta anual declarada pela empresa."""

import sqlalchemy as sa
from alembic import op

revision = "0015_company_revenue"
down_revision = "0014_password_recovery"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_revenues",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("company_revenues")
