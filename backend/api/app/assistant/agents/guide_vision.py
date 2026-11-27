import base64
from datetime import date
from decimal import Decimal
from time import monotonic

import httpx
from pydantic import field_serializer, field_validator

from app.assistant.agents.contracts import Contract
from app.assistant.schemas import Period
from app.config import Settings
from app.fiscal.schemas import Money
from app.llm_client import chat
from app.prompt_management import load_prompt, traced

MODEL = "deepseek-flash"


class GuideReading(Contract):
    period: Period | None
    due_date: date | None
    amount: Money | None

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_date(cls, value):
        if value is None or type(value) is date:
            return value
        if isinstance(value, str):
            parsed = date.fromisoformat(value)
            if parsed.isoformat() == value:
                return parsed
        raise ValueError("Use uma data em AAAA-MM-DD")

    @field_validator("amount", mode="before")
    @classmethod
    def decimal_string(cls, value):
        if value is not None and not isinstance(value, (str, Decimal)):
            raise ValueError("Use string decimal")
        return value

    @field_serializer("amount", when_used="json")
    def format_amount(self, value):
        return format(value, ".2f") if value is not None else None


@traced("assistant.guide")
def read_guide(
    settings: Settings,
    image: bytes,
    media_type: str,
    *,
    timeout: float,
    http_client: httpx.Client | None = None,
) -> tuple[GuideReading, dict]:
    started = monotonic()
    encoded = base64.b64encode(image).decode("ascii")
    prompt = load_prompt("assistant/guide")
    request = load_prompt("assistant/guide-request")
    response = chat(
        settings.model_copy(update={"llm_provider": "deepseek", "generation_model": MODEL}),
        [
            {"role": "system", "content": prompt.text},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request.text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                    },
                ],
            },
        ],
        prompt=prompt,
        prompt_versions={"assistant/guide-request": request.version},
        max_tokens=256,
        schema=GuideReading.model_json_schema(),
        timeout=timeout,
        http_client=http_client,
        deepseek_thinking=False,
    )
    reading = GuideReading.model_validate_json(response.texto)
    return reading, {
        "model": MODEL,
        "prompt_version": prompt.version,
        "input_tokens": response.tokens_in,
        "output_tokens": response.tokens_out,
        "latency_ms": round((monotonic() - started) * 1000),
        "monetary_cost": None,
    }
