"""Derived full text search for catalog queries without object downloads."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0005_legal_search"
down_revision = "0004_legal"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("norm_versions", sa.Column("search_vector", TSVECTOR(), nullable=True))
    op.create_index(
        "ix_norm_versions_search", "norm_versions", ["search_vector"], postgresql_using="gin"
    )


def downgrade():
    op.drop_index("ix_norm_versions_search", table_name="norm_versions")
    op.drop_column("norm_versions", "search_vector")
