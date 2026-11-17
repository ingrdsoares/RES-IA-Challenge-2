from app.config import Settings


def test_maximum_context_configuration_accepts_local_model_limit():
    settings = Settings(num_ctx=40960)
    assert settings.num_ctx == 40960
    assert settings.agent_token_budget >= 30 * 40960


def test_large_window_preserves_multiple_complete_passages():
    from app.assistant.agents.context import legal_payload

    passages = [{"text": "a" * 3000, "anchor_id": str(i)} for i in range(8)]
    payload = legal_payload("Pergunta", passages, Settings(num_ctx=40960))
    assert len(payload["sources"]) == 8
    assert all(len(p["text"]) == 3000 for p in payload["sources"].values())


def test_smaller_window_still_bounds_utf8_prompt_and_preserves_ids():
    import json

    from app.assistant.agents.context import legal_payload
    from app.assistant.agents.contracts import LegalResult
    from app.assistant.agents.llm import transport_schema
    from app.assistant.agents.prompts import PROMPTS

    settings = Settings(num_ctx=8192)
    payload = legal_payload(
        "Pergunta", [{"text": "🎉" * 3000, "anchor_id": str(i)} for i in range(8)], settings
    )
    assert 0 < sum(len(p["text"]) for p in payload["sources"].values()) < 24000
    size = len(
        (
            PROMPTS["legal"]
            + json.dumps(payload, ensure_ascii=False)
            + json.dumps(transport_schema(LegalResult.model_json_schema()))
        ).encode()
    )
    assert size <= 8192 - 1024 - 256
    assert payload["sources"]["legal:1"]["anchor_id"] == "0"
