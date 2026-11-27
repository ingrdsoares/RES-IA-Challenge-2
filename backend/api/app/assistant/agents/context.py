"""Fit legal evidence to the same conservative budget used by the model adapter."""

import json

from app.assistant.agents.contracts import LegalResult
from app.assistant.agents.llm import transport_schema
from app.assistant.agents.prompts import agent_prompt


def legal_payload(question, passages, settings):
    payload = {"question": question, "sources": {}}
    schema = json.dumps(transport_schema(LegalResult.model_json_schema()))
    budget = settings.num_ctx - settings.num_predict - 256
    prompt = agent_prompt("legal").text
    remaining = settings.max_context_chars
    for number, passage in enumerate(passages, 1):
        if remaining <= 0:
            break
        key = f"legal:{number}"
        low, high = 0, min(len(passage["text"]), remaining)
        while low < high:
            mid = (low + high + 1) // 2
            candidate = {
                **payload,
                "sources": {**payload["sources"], key: {**passage, "text": passage["text"][:mid]}},
            }
            size = len((prompt + json.dumps(candidate, ensure_ascii=False) + schema).encode())
            if size <= budget:
                low = mid
            else:
                high = mid - 1
        if not low:
            break
        payload["sources"][key] = {**passage, "text": passage["text"][:low]}
        remaining -= low
    return payload
