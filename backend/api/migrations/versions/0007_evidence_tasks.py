"""Declared evidence, private attachments and task history."""

import sqlalchemy as sa
from alembic import op

revision = "0007_evidence_tasks"
down_revision = "0006_assistant"
branch_labels = None
depends_on = None


def identifiers():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
    ]


def timestamps():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade():
    op.create_table(
        "obligations",
        *identifiers(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        timestamps(),
    )
    op.create_table(
        "evidence",
        *identifiers(),
        sa.Column("obligation_id", sa.Uuid(), sa.ForeignKey("obligations.id"), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("origin", sa.String(30), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        timestamps(),
    )
    op.create_table(
        "tasks",
        *identifiers(),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("source_step_index", sa.Integer(), nullable=True),
        timestamps(),
        sa.UniqueConstraint("source_message_id", "source_step_index"),
    )
    op.create_table(
        "task_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        timestamps(),
    )
    for table in ("obligations", "evidence", "tasks"):
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])


def downgrade():
    for table in ("task_events", "tasks", "evidence", "obligations"):
        op.drop_table(table)
