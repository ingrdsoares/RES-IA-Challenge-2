import pytest
from pydantic import ValidationError


def test_plan_rejects_unknown_duplicate_or_unbacked_agents():
    from app.assistant.agents.contracts import SupervisorPlan

    for agents in [["network"], ["legal", "legal"], ["planning"]]:
        with pytest.raises(ValidationError):
            SupervisorPlan(intent="question", agents=agents)


def test_actions_require_support_and_limit_three_steps():
    from app.assistant.agents.contracts import ActionPlan

    with pytest.raises(ValidationError):
        ActionPlan(actions=[{"title": "Pagar", "support_ids": []}])
    with pytest.raises(ValidationError):
        ActionPlan(actions=[{"title": "Conferir", "support_ids": ["legal:1"]}] * 4)


def test_model_cannot_confirm_conditions_or_select_company():
    from app.assistant.agents.contracts import SupervisorPlan

    for field in [{"company_id": "other"}, {"conditions_confirmed": True}]:
        with pytest.raises(ValidationError):
            SupervisorPlan(intent="fiscal", agents=["fiscal"], **field)


def test_plan_can_pause_for_required_financial_inputs():
    from app.assistant.agents.contracts import SupervisorPlan

    plan = SupervisorPlan(intent="calculation", agents=["fiscal"], missing_fields=["revenue"])
    assert plan.missing_fields == ["revenue"]
