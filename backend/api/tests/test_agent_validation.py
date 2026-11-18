import pytest


def test_invented_action_support_and_unmarked_legal_claim_are_rejected():
    from app.assistant.agents.validation import validate_results

    with pytest.raises(ValueError):
        validate_results(
            {"legal:1": {"text": "norma"}},
            {"claims": [{"text": "Regra", "support_ids": ["legal:1"]}]},
            {},
            {"actions": [{"title": "Conferir", "support_ids": ["legal:99"]}]},
            {"answer": "Regra [1]", "support_ids": ["legal:1"]},
        )
    with pytest.raises(ValueError):
        validate_results(
            {"legal:1": {"text": "norma"}},
            {"claims": [{"text": "Regra", "support_ids": ["legal:1"]}]},
            {},
            {"actions": []},
            {"answer": "Regra sem fonte", "support_ids": ["legal:1"]},
        )


def test_answer_cannot_use_support_not_used_by_specialists():
    from app.assistant.agents.validation import validate_results

    with pytest.raises(ValueError):
        validate_results(
            {"legal:1": {}},
            {"claims": []},
            {},
            {"actions": []},
            {"answer": "Texto [1]", "support_ids": ["legal:1"]},
        )


def test_legal_agent_cannot_claim_private_evidence_as_law():
    from app.assistant.agents.validation import validate_results

    with pytest.raises(ValueError):
        validate_results(
            {"evidence:e1": {}, "legal:1": {}},
            {"claims": [{"text": "Norma", "support_ids": ["evidence:e1", "legal:1"]}]},
            {},
            {"actions": []},
            {"answer": "Norma [1]", "support_ids": ["evidence:e1", "legal:1"]},
        )


def test_empty_legal_claims_do_not_publish_free_text_without_support():
    from app.assistant.agents.validation import render_answer

    result = render_answer(
        {"answer": "Você deve pagar R$ 999.", "legal_claims": []}, {}, False, True
    )
    assert "999" not in result
    assert "suficiente" in result
