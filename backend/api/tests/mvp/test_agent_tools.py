from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_agent_runs import seed_run


def test_calculation_tool_is_idempotent_and_rejects_changed_request(client):
    from app.assistant.agents.checkpoints import claim_step
    from app.assistant.agents.models import AgentRun
    from app.assistant.agents.tools import AgentTools
    from app.fiscal.models import Calculation

    factory = client.app.state.db_factory
    run_id, _ = seed_run(client)
    step = claim_step(factory, run_id, "fiscal", 0, {})
    with factory() as db:
        run = db.get(AgentRun, run_id)
    tools = AgentTools(
        factory,
        run.owner_id,
        run.company_id,
        {**run.context, "period": "2026-10"},
        client.app.state.settings,
    )
    request = {
        "kind": "simples",
        "period": "2026-10",
        "revenue": "1000.00",
        "rbt12": "12000.00",
        "conditions_confirmed": True,
    }
    first = tools.calculate(request, step.id)
    second = tools.calculate(request, step.id)
    assert first["id"] == second["id"]
    assert first["status"] == "rule_unavailable"
    assert first["result"] is None
    with pytest.raises(ValueError):
        tools.calculate({**request, "revenue": "2000.00"}, step.id)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Calculation)) == 1
    foreign = AgentTools(factory, uuid4(), run.company_id, run.context, client.app.state.settings)
    with pytest.raises(HTTPException) as error:
        foreign.fiscal_status("2026-10")
    assert error.value.status_code == 404
