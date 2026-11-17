from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from test_access import csrf
from test_conversations import conversation


def seed_run(client):
    from app.assistant.agents.models import AgentRun
    from app.jobs.models import Operation

    company, chat = conversation(client)
    operation_id = client.post(
        "/conversas/" + chat["id"] + "/mensagens",
        json={"text": "O que é MEI?"},
        headers={**csrf(client), "Idempotency-Key": "agent"},
    ).json()["operation_id"]
    with client.app.state.db_factory.begin() as db:
        operation = db.get(Operation, UUID(operation_id))
        from sqlalchemy import select

        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation.id))
        return run.id, operation.id


def test_run_and_stage_are_unique(client):
    from app.assistant.agents.models import AgentRun, AgentStep

    run_id, operation_id = seed_run(client)
    with client.app.state.db_factory() as db:
        run = db.get(AgentRun, run_id)
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                AgentRun(
                    operation_id=operation_id,
                    conversation_id=run.conversation_id,
                    company_id=run.company_id,
                    owner_id=run.owner_id,
                    context={},
                )
            )
            db.flush()
        db.add(AgentStep(run_id=run_id, revision=0, name="plan", input_hash="a" * 64))
        db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(AgentStep(run_id=run_id, revision=0, name="plan", input_hash="a" * 64))
            db.flush()


def test_migration_round_trip_on_new_database(monkeypatch):
    from pathlib import Path
    from uuid import uuid4

    import psycopg
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    database = "sd_agent_migration_" + uuid4().hex
    with psycopg.connect(
        "host=localhost port=15432 user=postgres password=sd_test_local dbname=postgres",
        autocommit=True,
    ) as admin:
        admin.execute("CREATE DATABASE " + database)
        try:
            url = "postgresql+psycopg://postgres:sd_test_local@localhost:15432/" + database
            monkeypatch.setenv("DATABASE_URL", url)
            config = Config(str(Path("backend/api/alembic.ini").resolve()))
            command.upgrade(config, "0010_telemetria_rag")
            command.upgrade(config, "head")
            engine = create_engine(url)
            with engine.connect() as connection:
                inspector = inspect(connection)
                assert {"agent_runs", "agent_steps", "legal_index_generations"} <= set(
                    inspector.get_table_names()
                )
                assert "actions" in {c["name"] for c in inspector.get_columns("messages")}
            engine.dispose()
            command.downgrade(config, "0010_telemetria_rag")
            command.upgrade(config, "head")
        finally:
            admin.execute("DROP DATABASE " + database + " WITH (FORCE)")
