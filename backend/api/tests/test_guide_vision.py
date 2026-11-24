import base64
import json
from decimal import Decimal

import httpx
import pytest
from app.assistant.agents.guide_vision import GuideReading, read_guide
from app.config import Settings
from app.errors import DependencyUnavailable
from pydantic import ValidationError


def test_deepseek_vision_sends_instruction_and_image():
    image = b"fixture"

    def respond(request):
        body = json.loads(request.content)
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert body["model"] == "deepseek-flash"
        text, attachment = body["messages"][-1]["content"]
        assert text["type"] == "text" and text["text"]
        assert attachment == {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()},
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "period": "2026-10", "due_date": "2026-11-20", "amount": "81.05",
        })}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        reading, usage = read_guide(
            Settings(deepseek_api_key="test-key"), image, "image/png", timeout=2, http_client=client
        )
    assert reading.period == "2026-10"
    assert reading.due_date.isoformat() == "2026-11-20"
    assert reading.amount == Decimal("81.05")
    assert usage["model"] == "deepseek-flash"


@pytest.mark.parametrize("change", [
    {"period": "2026-13"}, {"due_date": "2026-02-31"}, {"amount": 81.05}, {"amount": "-1"},
])
def test_guide_reading_handles_null_fields_and_rejects_invalid_values(change):
    fields = {"period": None, "due_date": None, "amount": None}
    assert GuideReading.model_validate(fields).model_dump() == fields
    with pytest.raises(ValidationError):
        GuideReading.model_validate(fields | change)
    with pytest.raises(ValidationError):
        GuideReading.model_validate_json("inválido")


def test_guide_provider_error_does_not_echo_response():
    def respond(request):
        return httpx.Response(503, text="image-and-api-key")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(DependencyUnavailable, match="HTTP 503") as error:
            read_guide(Settings(deepseek_api_key="test-key"), b"image", "image/png", timeout=2,
                       http_client=client)
    assert "image-and-api-key" not in str(error.value)
