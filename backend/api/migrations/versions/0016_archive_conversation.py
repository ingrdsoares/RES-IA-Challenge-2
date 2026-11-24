"""Arquivamento de conversas."""

import sqlalchemy as sa
from alembic import op

revision = "0016_archive_conversation"
down_revision = "0015_company_revenue"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conversations", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("conversations", "archived_at")
