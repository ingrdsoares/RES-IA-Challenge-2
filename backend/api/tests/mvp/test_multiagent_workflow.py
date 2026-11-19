from uuid import UUID

from test_access import csrf
from test_conversations import conversation


class Model:
    def generate(self, role, schema, payload, timeout, output_tokens):
        replies = {
            "plan": {"intent": "status", "agents": ["fiscal", "planning"]},
            "fiscal": {"status": "answered", "claims": []},
            "planning": {"actions": []},
            "synthesis": {"answer": "Verificação oficial não realizada.", "support_ids": []},
        }
        return schema.model_validate(replies[role]), {"input_tokens": 10, "output_tokens": 10}


def test_full_run_persists_checkpoints_and_replay_has_one_answer(client):
    from app.assistant.agents.executor import execute_run
    from app.assistant.agents.models import AgentRun, AgentStep
    from sqlalchemy import select

    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    response = client.post(
        url,
        json={"text": "Minha empresa está regular?"},
        headers={**csrf(client), "Idempotency-Key": "multi"},
    ).json()
    factory = client.app.state.db_factory
    operation_id = UUID(response["operation_id"])
    execute_run(factory, operation_id, model=Model(), settings=client.app.state.settings)
    execute_run(factory, operation_id, model=Model(), settings=client.app.state.settings)
    messages = client.get(url).json()["items"]
    assert len(messages) == 2
    assert "não verificada" in messages[-1]["text"]
    # The interface renders the deterministic fiscal facts next to the answer.
    assert set(messages[-1]["context"]["fiscal_status"]) >= {"registration", "obligations"}
    with factory() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
        assert run.status == "succeeded"
        steps = db.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all()
        assert {step.name for step in steps} == {"plan", "fiscal", "planning", "synthesis"}
        assert all(step.status == "succeeded" for step in steps)


def test_run_awaits_and_resumes_same_identity(client):
    from app.assistant.agents.executor import execute_run
    from app.assistant.agents.models import AgentRun
    from sqlalchemy import select

    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    response = client.post(
        url, json={"text": "Paguei o DAS?"}, headers={**csrf(client), "Idempotency-Key": "await"}
    ).json()
    factory = client.app.state.db_factory
    operation_id = UUID(response["operation_id"])
    with factory() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
        assert run.status == "awaiting_data"
        run_id = run.id
    confirmed = client.post(
        url,
        json={
            "text": "Confirmo",
            "confirmation_for": str(operation_id),
            "confirmation": {"period": "2026-10"},
        },
        headers={**csrf(client), "Idempotency-Key": "confirmation"},
    )
    assert confirmed.status_code == 202
    execute_run(factory, operation_id, model=Model(), settings=client.app.state.settings)
    with factory() as db:
        run = db.get(AgentRun, run_id)
        assert run.status == "succeeded"
        assert run.revision == 1
        assert run.context["period"] == "2026-10"


def test_api_exposes_run_summary_without_private_checkpoints(client):
    company, chat = conversation(client)
    response = client.post(
        "/conversas/" + chat["id"] + "/mensagens",
        json={"text": "Minha situação?"},
        headers={**csrf(client), "Idempotency-Key": "summary"},
    ).json()
    assert response["run_id"]
    assert response["trace_id"]
    status = client.get(response["status_url"]).json()
    assert status["run"]["run_id"] == response["run_id"]
    assert "context" not in status["run"]
    assert "token" not in status["run"]


def test_financial_confirmation_preserves_decimal_and_updates_snapshot_only(client):
    from app.assistant.agents.models import AgentRun
    from app.assistant.models import Message
    from app.jobs.models import Operation
    from sqlalchemy import select

    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    response = client.post(
        url, json={"text": "Quanto devo?"}, headers={**csrf(client), "Idempotency-Key": "financial"}
    ).json()
    factory = client.app.state.db_factory
    operation_id = UUID(response["operation_id"])
    with factory.begin() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
        run.context = {
            **run.context,
            "missing_fields": [
                "period",
                "kind",
                "revenue",
                "rbt12",
                "conditions_confirmed",
                "regime",
            ],
        }
        user = db.scalar(select(Message).where(Message.operation_id == operation_id))
        user.context = run.context
    confirm = {
        "period": "2026-10",
        "kind": "simples",
        "revenue": "1000.00",
        "rbt12": "12000.00",
        "conditions_confirmed": True,
        "regime": "simples",
    }
    result = client.post(
        url,
        json={
            "text": "Confirmo os dados",
            "confirmation_for": str(operation_id),
            "confirmation": confirm,
        },
        headers={**csrf(client), "Idempotency-Key": "financial-confirm"},
    )
    assert result.status_code == 202
    with factory() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
        assert run.context["calculation_input"]["revenue"] == "1000.00"
        assert run.context["company"]["regime"] == "simples"
        assert db.get(Operation, operation_id).status == "queued"


def test_failed_stage_is_retryable_without_repeating_completed_plan(client):
    import httpx
    from app.assistant.agents.executor import execute_run
    from app.assistant.agents.models import AgentRun, AgentStep
    from sqlalchemy import select

    company, chat = conversation(client)
    response = client.post(
        "/conversas/" + chat["id"] + "/mensagens",
        json={"text": "Situação da empresa?"},
        headers={**csrf(client), "Idempotency-Key": "retry"},
    ).json()
    factory = client.app.state.db_factory
    operation_id = UUID(response["operation_id"])

    class Flaky(Model):
        broken = True

        def generate(self, role, schema, payload, timeout, output_tokens):
            if role == "fiscal" and self.broken:
                self.broken = False
                raise httpx.ConnectError("secret")
            return super().generate(role, schema, payload, timeout, output_tokens)

    model = Flaky()
    execute_run(factory, operation_id, model=model, settings=client.app.state.settings)
    execute_run(factory, operation_id, model=model, settings=client.app.state.settings)
    with factory() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
        assert run.status == "succeeded"
        steps = {s.name: s for s in db.scalars(select(AgentStep).where(AgentStep.run_id == run.id))}
        assert steps["plan"].attempts == 1
        assert steps["fiscal"].attempts == 2


def test_tool_snapshot_is_reused_when_inference_retries(client):
    import httpx
    from app.assistant.agents.executor import execute_run
    from app.assistant.agents.models import AgentRun
    from sqlalchemy import select

    company, chat = conversation(client)
    response = client.post(
        "/conversas/" + chat["id"] + "/mensagens",
        json={"text": "Situação?"},
        headers={**csrf(client), "Idempotency-Key": "snapshot-retry"},
    ).json()
    factory = client.app.state.db_factory

    class Tools:
        def fiscal_status(self, period):
            return {
                scope: {"latest_evidence": None, "verification": "unverified"}
                for scope in ("registration", "federal_certificate", "obligations")
            }

    class Broken(Model):
        def generate(self, role, schema, payload, timeout, output_tokens):
            if role == "fiscal":
                raise httpx.ConnectError("transient")
            return super().generate(role, schema, payload, timeout, output_tokens)

    operation_id = UUID(response["operation_id"])
    execute_run(
        factory, operation_id, model=Broken(), tools=Tools(), settings=client.app.state.settings
    )

    class ChangedTools:
        def fiscal_status(self, period):
            raise AssertionError("Snapshot should be preserved")

    execute_run(
        factory,
        operation_id,
        model=Model(),
        tools=ChangedTools(),
        settings=client.app.state.settings,
    )
    with factory() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
        assert run.status == "succeeded"


def test_restart_after_synthesis_checkpoint_publishes_once(client, monkeypatch):
    from datetime import UTC, datetime, timedelta

    import app.assistant.agents.executor as executor
    import pytest
    from app.assistant.agents.models import AgentRun
    from app.jobs.models import Operation
    from app.jobs.outbox import dispatch
    from sqlalchemy import select

    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    response = client.post(
        url,
        json={"text": "Minha situação?"},
        headers={**csrf(client), "Idempotency-Key": "crash-final"},
    ).json()
    factory = client.app.state.db_factory
    operation_id = UUID(response["operation_id"])
    render = executor.render_answer

    def crash(*args):
        raise SystemExit("simulated worker termination")

    monkeypatch.setattr(executor, "render_answer", crash)
    with pytest.raises(SystemExit):
        executor.execute_run(
            factory, operation_id, model=Model(), settings=client.app.state.settings
        )
    with factory.begin() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
        run.deadline = datetime.now(UTC) - timedelta(seconds=1)
        db.get(Operation, operation_id).dispatched_at = datetime.now(UTC) - timedelta(seconds=40)
    assert dispatch(factory, client.app.state.redis) == 1
    monkeypatch.setattr(executor, "render_answer", render)
    executor.execute_run(factory, operation_id, model=Model(), settings=client.app.state.settings)
    assert client.get(response["status_url"]).json()["status"] == "succeeded"
    assert len(client.get(url).json()["items"]) == 2


def test_discarded_fiscal_prose_does_not_override_server_rendering(client):
    from app.assistant.agents.executor import execute_run

    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    receipt = client.post(
        url,
        json={"text": "Minha situação fiscal?"},
        headers={**csrf(client), "Idempotency-Key": "fiscal-render"},
    ).json()

    class Prose(Model):
        def generate(self, role, schema, payload, timeout, output_tokens):
            if role == "synthesis":
                return schema.model_validate(
                    {"answer": "Valor inventado R$ 999 [1]", "support_ids": []}
                ), {}
            return super().generate(role, schema, payload, timeout, output_tokens)

    execute_run(
        client.app.state.db_factory,
        UUID(receipt["operation_id"]),
        model=Prose(),
        settings=client.app.state.settings,
    )
    assert client.get(receipt["status_url"]).json()["status"] == "succeeded"
    answer = client.get(url).json()["items"][-1]
    assert "999" not in answer["text"]
    assert "[1]" not in answer["text"]
    assert "não verificada" in answer["text"]


def test_legal_citations_keep_inline_numbering(client):
    from app.assistant.agents.executor import execute_run

    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    receipt = client.post(
        url,
        json={"text": "O que diz a LC 123 sobre o DAS?"},
        headers={**csrf(client), "Idempotency-Key": "legal-numbering"},
    ).json()

    class Tools:
        def legal(self, question):
            return [{"title": f"Fonte {n}", "text": f"Trecho {n}"} for n in (1, 2, 3)]

    class Legal(Model):
        def generate(self, role, schema, payload, timeout, output_tokens):
            replies = {
                "plan": {"intent": "norma", "agents": ["legal"]},
                "legal": {
                    "status": "answered",
                    "claims": [{"text": "Regra do DAS.", "support_ids": ["legal:3"]}],
                },
                "synthesis": {"answer": "Regra do DAS [3].", "support_ids": ["legal:3"]},
            }
            return schema.model_validate(replies[role]), {}

    execute_run(
        client.app.state.db_factory,
        UUID(receipt["operation_id"]),
        model=Legal(),
        tools=Tools(),
        settings=client.app.state.settings,
    )
    answer = client.get(url).json()["items"][-1]
    assert "[3]" in answer["text"]
    assert [(c["title"], c["citation_index"]) for c in answer["citations"]] == [("Fonte 3", 3)]
