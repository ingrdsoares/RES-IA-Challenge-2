import json
import time

import ollama

from app.assistant.agents.prompts import PROMPTS, VERSION


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
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client

    def generate(self, role, schema, payload, timeout, output_tokens):
        prompt = PROMPTS[role]
        content = json.dumps(payload, ensure_ascii=False)
        grammar = transport_schema(schema.model_json_schema())
        # Conservative one byte per token bound, including transport schema.
        if (
            len((prompt + content + json.dumps(grammar)).encode())
            > self.settings.num_ctx - output_tokens - 256
        ):
            raise ValueError("Contexto dos agentes excede orçamento")
        owned = self.client is None
        client = self.client or ollama.Client(host=str(self.settings.ollama_url), timeout=timeout)
        started = time.monotonic()
        try:
            response = client.chat(
                model=self.settings.generation_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content},
                ],
                format=grammar,
                stream=False,
                think=False,
                options={
                    "temperature": 0,
                    "seed": 42,
                    "num_ctx": self.settings.num_ctx,
                    "num_predict": output_tokens,
                },
            )
            result = schema.model_validate_json(response.message.content)
            return result, {
                "model": self.settings.generation_model,
                "prompt_version": VERSION,
                "input_tokens": response.prompt_eval_count,
                "output_tokens": response.eval_count,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "monetary_cost": None,
            }
        finally:
            if owned:
                client.close()
