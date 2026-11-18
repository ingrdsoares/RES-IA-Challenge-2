import httpx
import ollama
import pytest
from app.config import Settings
from pydantic import ValidationError


def test_model_validates_json_and_records_measured_tokens():
    from app.assistant.agents.contracts import SupervisorPlan
    from app.assistant.agents.llm import AgentModel

    def respond(request):
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {
                    "role": "assistant",
                    "content": '{"intent":"legal","agents":["legal"]}',
                },
                "done": True,
                "prompt_eval_count": 20,
                "eval_count": 10,
            },
        )

    client = ollama.Client(transport=httpx.MockTransport(respond))
    result, usage = AgentModel(Settings(), client).generate(
        "plan", SupervisorPlan, {"question": "MEI"}, 10, 256
    )
    assert result.agents == ["legal"]
    assert usage["input_tokens"] == 20
    assert usage["output_tokens"] == 10
    client.close()


def test_invalid_model_output_is_not_trusted():
    from app.assistant.agents.contracts import SupervisorPlan
    from app.assistant.agents.llm import AgentModel

    client = ollama.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "message": {
                        "role": "assistant",
                        "content": '{"intent":"legal","agents":["shell"]}',
                    },
                    "done": True,
                },
            )
        )
    )
    with pytest.raises(ValidationError):
        AgentModel(Settings(), client).generate("plan", SupervisorPlan, {}, 10, 256)
    client.close()


def test_transport_keeps_title_field_while_removing_schema_title_annotation():
    from app.assistant.agents.llm import transport_schema

    source = {
        "title": "Envelope",
        "type": "object",
        "properties": {"title": {"title": "Action title", "type": "string", "maxLength": 500}},
    }
    assert transport_schema(source) == {
        "type": "object",
        "properties": {"title": {"type": "string"}},
    }
