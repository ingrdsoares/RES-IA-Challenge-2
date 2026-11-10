"""Immutable legal document catalog."""

import sqlalchemy as sa
from alembic import op

revision = "0004_legal"
down_revision = "0003_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "norms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_key", sa.String(256), nullable=False, unique=True),
    )
    op.create_table(
        "norm_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("norms.id"), nullable=False),
        *[
            sa.Column(name, sa.String(256), nullable=False)
            for name in ("version_label", "title", "authority", "norm_type")
        ],
        sa.Column("subjects", sa.JSON(), nullable=False),
        sa.Column("official_url", sa.String(2048), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("metadata_hash", sa.String(64), nullable=False),
        sa.Column("original_key", sa.String(512), nullable=False),
        sa.Column("json_key", sa.String(512), nullable=True),
        sa.Column("anchors", sa.JSON(), nullable=False),
        sa.Column("media_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "version_label"),
    )
    op.create_index("ix_norm_versions_document_id", "norm_versions", ["document_id"])


def downgrade():
    op.drop_table("norm_versions")
    op.drop_table("norms")
