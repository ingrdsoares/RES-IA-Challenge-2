"""Links de recuperação de senha de uso único."""

import sqlalchemy as sa
from alembic import op

revision = "0011_password_recovery"
down_revision = "0010_telemetria_rag"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("reset_token_hash", sa.String(64), nullable=True))
    op.add_column(
        "accounts", sa.Column("reset_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint("uq_accounts_reset_token_hash", "accounts", ["reset_token_hash"])


def downgrade():
    op.drop_constraint("uq_accounts_reset_token_hash", "accounts", type_="unique")
    op.drop_column("accounts", "reset_expires_at")
    op.drop_column("accounts", "reset_token_hash")
