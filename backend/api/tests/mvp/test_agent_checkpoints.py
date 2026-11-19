from datetime import UTC, datetime, timedelta

import pytest
from test_agent_runs import seed_run


def test_completed_stage_survives_retry_and_late_writer_is_rejected(client):
    from app.assistant.agents.checkpoints import StaleLease, claim_step, finish_step
    from app.assistant.agents.models import AgentStep

    factory = client.app.state.db_factory
    run_id, _ = seed_run(client)
    first = claim_step(factory, run_id, "plan", 0, {"question": "MEI"})
    with factory.begin() as db:
        db.get(AgentStep, first.id).lease_until = datetime.now(UTC) - timedelta(seconds=1)
    second = claim_step(factory, run_id, "plan", 0, {"question": "MEI"})
    with pytest.raises(StaleLease):
        finish_step(factory, first.id, first.token, {"bad": True}, {})
    finish_step(factory, second.id, second.token, {"intent": "legal"}, {})
    cached = claim_step(factory, run_id, "plan", 0, {"question": "MEI"})
    assert cached.result == {"intent": "legal"}
    assert cached.attempts == 2


def test_live_claim_defers_other_worker_and_changed_input_is_rejected(client):
    from app.assistant.agents.checkpoints import claim_step
    from app.jobs.errors import JobDeferred

    factory = client.app.state.db_factory
    run_id, _ = seed_run(client)
    claim_step(factory, run_id, "plan", 0, {"question": "MEI"})
    with pytest.raises(JobDeferred):
        claim_step(factory, run_id, "plan", 0, {"question": "MEI"})
    with pytest.raises(ValueError):
        claim_step(factory, run_id, "plan", 0, {"question": "other"})


def test_expired_deadline_and_call_budget_stop_new_inference(client):
    from app.assistant.agents.checkpoints import BudgetExceeded, claim_step
    from app.assistant.agents.models import AgentRun

    factory = client.app.state.db_factory
    run_id, _ = seed_run(client)
    with factory.begin() as db:
        db.get(AgentRun, run_id).calls = 30
    with pytest.raises(BudgetExceeded):
        claim_step(factory, run_id, "plan", 0, {})


def test_other_run_in_same_company_waits_between_stages(client):
    from app.assistant.agents.checkpoints import claim_step, finish_step
    from app.assistant.agents.models import AgentRun
    from app.jobs.errors import JobDeferred
    from app.jobs.models import Operation

    factory = client.app.state.db_factory
    run_id, _ = seed_run(client)
    first = claim_step(factory, run_id, "plan", 0, {})
    finish_step(factory, first.id, first.token, {}, {})
    with factory.begin() as db:
        first_run = db.get(AgentRun, run_id)
        operation = Operation(
            owner_id=first_run.owner_id,
            company_id=first_run.company_id,
            scope=str(first_run.company_id),
            kind="assistant.answer",
            key="second",
            payload={},
            payload_hash="b" * 64,
        )
        db.add(operation)
        db.flush()
        second = AgentRun(
            owner_id=first_run.owner_id,
            company_id=first_run.company_id,
            conversation_id=first_run.conversation_id,
            operation_id=operation.id,
            context={},
        )
        db.add(second)
        db.flush()
        second_id = second.id
    with pytest.raises(JobDeferred):
        claim_step(factory, second_id, "plan", 0, {})
