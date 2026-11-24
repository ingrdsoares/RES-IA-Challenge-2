"""Preferência de lembretes por e-mail; desligada até a pessoa ativar."""

import sqlalchemy as sa
from alembic import op

revision = "0018_reminders"
down_revision = "0017_monthly_revenue"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounts",
        sa.Column("reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("accounts", "reminders_enabled")
