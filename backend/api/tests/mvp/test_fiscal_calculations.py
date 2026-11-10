from decimal import Decimal

import pytest

MEI = {
    "salary": "1000.00",
    "inss_rate": "0.05",
    "icms": "1.00",
    "iss": "5.00",
    "activities": {"6201501": "services"},
    "limitations": ["Synthetic fixture; not fiscal advice"],
}
SIMPLES = {
    "activities": {"6201501": {"annex": "III", "factor_r": True}},
    "factor_r_threshold": "0.28",
    "rate_places": 8,
    "annexes": {
        "III": [
            {
                "upper": "1000000.00",
                "rate": "0.10",
                "deduction": "10000.00",
                "shares": {"one": "0.6", "two": "0.4"},
            }
        ],
        "V": [{"upper": "1000000.00", "rate": "0.20", "deduction": "10000.00", "shares": {}}],
    },
    "limitations": ["Synthetic fixture; excludes special cases"],
}


def test_mei_uses_decimal_parameters():
    from app.fiscal.mei import simulate_mei
    from app.fiscal.schemas import CalculationInput

    result = simulate_mei(
        CalculationInput(
            kind="mei", period="2026-10", activity="services", conditions_confirmed=True
        ),
        MEI,
        "6201501",
    )
    assert result["amount"] == "55.00"
    assert result["components"] == {"inss": "50.00", "icms": "0.00", "iss": "5.00"}


@pytest.mark.parametrize(
    "payroll,annex,amount", [("140000.00", "III", "800.00"), ("139999.99", "V", "1800.00")]
)
def test_factor_r_is_not_rounded_before_comparison(payroll, annex, amount):
    from app.fiscal.schemas import CalculationInput
    from app.fiscal.simples import simulate_simples

    result = simulate_simples(
        CalculationInput(
            kind="simples",
            period="2026-10",
            rbt12="500000.00",
            revenue="10000.00",
            payroll12=payroll,
            conditions_confirmed=True,
        ),
        SIMPLES,
        "6201501",
    )
    assert result["annex"] == annex
    assert result["amount"] == amount
    if annex == "III":
        assert sum(Decimal(v) for v in result["components"].values()) == Decimal(amount)


def test_zero_revenue_does_not_invent_rule():
    from app.fiscal.schemas import CalculationInput
    from app.fiscal.simples import simulate_simples

    with pytest.raises(ValueError):
        simulate_simples(
            CalculationInput(
                kind="simples",
                period="2026-10",
                rbt12="0",
                revenue="100",
                payroll12="0",
                conditions_confirmed=True,
            ),
            SIMPLES,
            "6201501",
        )


def test_reviewed_calculation_reaches_chat_without_llm_arithmetic(client):
    from uuid import UUID

    from app.assistant.orchestrator import answer_message
    from app.fiscal.registry import import_rule, review_rule
    from app.fiscal.schemas import RuleInput
    from app.jobs.worker import execute
    from test_access import csrf
    from test_conversations import conversation

    company, chat = conversation(client)
    with client.app.state.db_factory() as db:
        rule = import_rule(
            db,
            RuleInput(
                kind="mei",
                version="synthetic",
                valid_from="2026-01",
                valid_to="2026-12",
                parameters=MEI,
                references=["https://example.org/synthetic"],
            ),
        )
        review_rule(db, rule.id, "Test reviewer", "Synthetic test review")
        db.commit()
    response = client.post(
        "/conversas/" + chat["id"] + "/mensagens",
        json={
            "text": "Calcular simulação",
            "calculation": {
                "kind": "mei",
                "period": "2026-10",
                "activity": "services",
                "conditions_confirmed": True,
            },
        },
        headers={**csrf(client), "Idempotency-Key": "calculate"},
    )
    assert response.status_code == 202
    client.patch("/empresas/" + company["id"], json={"cnae": "9999999"}, headers=csrf(client))

    def forbidden(prompt):
        pytest.fail("LLM must not calculate this amount")

    execute(
        client.app.state.db_factory,
        UUID(response.json()["operation_id"]),
        {
            "assistant.answer": lambda db, operation: answer_message(
                db, operation, generate=forbidden
            )
        },
    )
    messages = client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"]
    assert messages[-1]["context"]["calculation"]["result"]["amount"] == "55.00"
    assert messages[-1]["context"]["calculation"]["result"]["rule_version"] == "synthetic"
    assert "55.00" in messages[-1]["text"]
