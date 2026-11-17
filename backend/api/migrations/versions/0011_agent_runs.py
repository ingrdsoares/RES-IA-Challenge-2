"""Durable multiagent runs and fenced stages."""

import sqlalchemy as sa
from alembic import op

revision = "0011_agent_runs"
down_revision = "0010_telemetria_rag"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("action_support", sa.JSON(), nullable=True))
    op.add_column("messages", sa.Column("actions", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "operation_id", sa.Uuid(), sa.ForeignKey("operations.id"), nullable=False, unique=True
        ),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("revisions", sa.JSON(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("confirmations", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_runs_company_id", "agent_runs", ["company_id"])
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(30), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("token", sa.Uuid()),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("result", sa.JSON()),
        sa.Column("error", sa.String(80)),
        sa.Column("model", sa.String(120)),
        sa.Column("prompt_version", sa.String(40)),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "revision", "name"),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.add_column(
        "calculations", sa.Column("agent_step_id", sa.Uuid(), sa.ForeignKey("agent_steps.id"))
    )
    op.create_unique_constraint("uq_calculations_agent_step", "calculations", ["agent_step_id"])


def downgrade():
    op.drop_column("tasks", "action_support")
    op.drop_column("messages", "actions")
    op.drop_constraint("uq_calculations_agent_step", "calculations", type_="unique")
    op.drop_column("calculations", "agent_step_id")
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
