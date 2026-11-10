"""Explicit territorial scope; unknown scope stays ineligible for RAG."""

import sqlalchemy as sa
from alembic import op

revision = "0009_norm_jurisdiction"
down_revision = "0008_fiscal"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("norm_versions", sa.Column("jurisdiction", sa.String(5), nullable=True))


def downgrade():
    op.drop_column("norm_versions", "jurisdiction")
