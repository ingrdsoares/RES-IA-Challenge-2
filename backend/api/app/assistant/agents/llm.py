import json
import time

from app.assistant.agents.prompts import agent_prompt
from app.llm_client import chat


def transport_schema(value):
    if isinstance(value, dict):
        return {
            key: (
                {name: transport_schema(child) for name, child in item.items()}
                if key in {"properties", "$defs"}
                else transport_schema(item)
            )
            for key, item in value.items()
            if key not in {"title", "minLength", "maxLength", "minItems", "maxItems"}
        }
    if isinstance(value, list):
        return [transport_schema(item) for item in value]
    return value


class AgentModel:
    def __init__(self, settings, client=None, http_client=None):
        self.settings = settings
        self.client = client
        self.http_client = http_client

    def generate(self, role, schema, payload, timeout, output_tokens):
        prompt = agent_prompt(role)
        content = json.dumps(payload, ensure_ascii=False)
        grammar = transport_schema(schema.model_json_schema())
        # Conservative one byte per token bound, including transport schema.
        if (
            len((prompt.text + content + json.dumps(grammar)).encode())
            > self.settings.num_ctx - output_tokens - 256
        ):
            raise ValueError("Contexto dos agentes excede orçamento")
        started = time.monotonic()
        response = chat(
            self.settings,
            [
                {"role": "system", "content": prompt.text},
                {"role": "user", "content": content},
            ],
            prompt=prompt,
            max_tokens=output_tokens,
            schema=grammar,
            timeout=timeout,
            ollama_client=self.client,
            http_client=self.http_client,
        )
        result = schema.model_validate_json(response.texto)
        return result, {
            "model": self.settings.generation_model,
            "prompt_version": prompt.version,
            "input_tokens": response.tokens_in,
            "output_tokens": response.tokens_out,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "monetary_cost": None,
        }
