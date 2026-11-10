from test_access import csrf
from test_conversations import conversation


def test_unreviewed_rules_never_calculate(client):
    from app.fiscal.registry import import_rule
    from app.fiscal.schemas import RuleInput

    company, _ = conversation(client)
    with client.app.state.db_factory() as db:
        import_rule(
            db,
            RuleInput(
                kind="mei",
                version="synthetic",
                valid_from="2026-01",
                valid_to="2026-12",
                parameters={},
                references=["https://example.org/test"],
            ),
        )
        db.commit()
    response = client.post(
        "/empresas/" + company["id"] + "/calculos",
        json={"kind": "mei", "period": "2026-10"},
        headers=csrf(client),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "rule_unavailable"
    assert response.json()["result"] is None


def test_invalid_money_rejected(client):
    company, _ = conversation(client)
    for value in ("-1.00", "NaN", "Infinity", "1.234"):
        response = client.post(
            "/empresas/" + company["id"] + "/calculos",
            json={"kind": "simples", "period": "2026-10", "rbt12": value},
            headers=csrf(client),
        )
        assert response.status_code == 422


def test_reviewed_rule_versions_cannot_overlap(client):
    import pytest
    from app.fiscal.registry import import_rule, review_rule
    from app.fiscal.schemas import RuleInput
    from fastapi import HTTPException

    with client.app.state.db_factory() as db:
        data = RuleInput(
            kind="mei",
            version="first",
            valid_from="2026-01",
            valid_to="2026-12",
            parameters={},
            references=["https://example.org/synthetic"],
        )
        one = import_rule(db, data)
        review_rule(db, one.id, "Synthetic test reviewer", "Synthetic review fixture")
        two = import_rule(db, data.model_copy(update={"version": "second"}))
        with pytest.raises(ValueError, match="sobrepõe"):
            review_rule(db, two.id, "Synthetic reviewer", "Synthetic review")
        with pytest.raises(HTTPException):
            import_rule(db, data.model_copy(update={"parameters": {"changed": True}}))
