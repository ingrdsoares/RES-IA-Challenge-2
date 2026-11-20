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


def test_render_answer_aligns_model_citations_to_legal_support_ids():
    from app.assistant.agents.validation import render_answer, validate_results

    # Caso A03: modelo escreveu [1], mas o suporte legal é legal:3
    final = {
        "answer": "O recolhimento mensal do MEI compreende a contribuição fixa de R$ 45,65 [1].",
        "legal_claims": [{"text": "O recolhimento mensal...", "support_ids": ["legal:3"]}],
        "support_ids": ["legal:3"],
    }
    rendered = render_answer(final, {}, False, has_legal=True)
    assert "[3]" in rendered
    assert "[1]" not in rendered

    # Validação aceita o texto renderizado
    final["answer"] = rendered
    support = {"legal:3": {"text": "lei"}}
    legal = {"claims": final["legal_claims"]}
    validated = validate_results(support, legal, {}, {"actions": []}, final)
    assert validated["answer"] == rendered


def test_render_answer_aligns_multiple_citations_and_covers_missing():
    from app.assistant.agents.validation import render_answer, validate_results

    # Caso A12: modelo escreveu [1], mas suporte é legal:3 e legal:5
    final = {
        "answer": "Abrir um CNPJ não torna automaticamente optante pelo Simples Nacional [1].",
        "legal_claims": [
            {
                "text": "Abrir um CNPJ...",
                "support_ids": ["legal:3", "legal:5"],
            }
        ],
        "support_ids": ["legal:3", "legal:5"],
    }
    rendered = render_answer(final, {}, False, has_legal=True)
    assert "[3]" in rendered
    assert "[5]" in rendered

    final["answer"] = rendered
    support = {"legal:3": {}, "legal:5": {}}
    legal = {"claims": final["legal_claims"]}
    validated = validate_results(support, legal, {}, {"actions": []}, final)
    assert "[3]" in validated["answer"] and "[5]" in validated["answer"]


def test_render_answer_adds_citations_when_model_omits_brackets():
    from app.assistant.agents.validation import render_answer

    final = {
        "answer": "O MEI é um regime simplificado.",
        "legal_claims": [{"text": "O MEI...", "support_ids": ["legal:2"]}],
        "support_ids": ["legal:2"],
    }
    rendered = render_answer(final, {}, False, has_legal=True)
    assert rendered.endswith("[2].")


def test_audit_seven_failures_are_resolved():
    import json
    from pathlib import Path

    from app.assistant.agents.validation import render_answer, validate_results

    audit_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "avaliacao"
        / "2026-11-17-auditoria-recuperacao-sete-falhas-thinking.json"
    )
    if not audit_path.exists():
        pytest.skip("Audit file not found")

    with open(audit_path, encoding="utf-8") as f:
        audit = json.load(f)

    support = {f"legal:{i}": {"text": "dummy"} for i in range(1, 10)}

    for case in audit["cases"]:
        legal = case["legal_result"]
        synthesis = case["synthesis_result"]
        specialist_used = {
            ref for claim in legal.get("claims", []) for ref in claim.get("support_ids", [])
        }
        final = dict(synthesis)

        if not legal.get("claims"):
            final["legal_claims"] = []
            final["support_ids"] = []
            final["answer"] = render_answer(final, support, False, True)
        else:
            final["legal_claims"] = legal.get("claims", [])
            synthesis_refs = [r for r in final.get("support_ids", []) if r in specialist_used]
            legal_refs = sorted(
                {
                    r
                    for claim in legal.get("claims", [])
                    for r in claim.get("support_ids", [])
                    if r.startswith("legal:")
                }
            )
            final["support_ids"] = sorted(set(synthesis_refs) | set(legal_refs))
            final["answer"] = render_answer(final, support, False, True)

        val = validate_results(support, legal, {}, {"actions": []}, final)
        assert isinstance(val["answer"], str)
        if legal.get("claims"):
            assert len(val["support_ids"]) > 0
        else:
            assert val["support_ids"] == []
            assert "suficiente" in val["answer"]
