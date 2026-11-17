"""Persist tool snapshots in migrated databases as well as ORM-created schemas."""

import sqlalchemy as sa
from alembic import op

revision = "0013_agent_tool_result"
down_revision = "0012_legal_hybrid"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agent_steps", sa.Column("tool_result", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("agent_steps", "tool_result")
