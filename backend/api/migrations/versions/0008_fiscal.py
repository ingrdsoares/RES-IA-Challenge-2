"""Reviewed rules and auditable calculation snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0008_fiscal"
down_revision = "0007_evidence_tasks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fiscal_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("valid_from", sa.String(7), nullable=False),
        sa.Column("valid_to", sa.String(7), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewed_by", sa.String(120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_evidence", sa.String(512), nullable=True),
        sa.UniqueConstraint("kind", "version"),
    )
    op.create_table(
        "calculations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("rule_id", sa.Uuid(), sa.ForeignKey("fiscal_rules.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("company_snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(256), nullable=True),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_calculations_company_id", "calculations", ["company_id"])


def downgrade():
    op.drop_table("calculations")
    op.drop_table("fiscal_rules")
