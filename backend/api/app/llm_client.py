"""Geração de texto pelo provedor configurado: Ollama local ou API compatível com OpenAI."""

import json
from dataclasses import dataclass

import httpx
import ollama

from app.config import Settings
from app.errors import DependencyUnavailable, dependency_errors

_NOMES = {"ollama": "Ollama", "google": "Google Gemini", "deepseek": "DeepSeek"}


@dataclass
class Resposta:
    texto: str
    tokens_in: int | None
    tokens_out: int | None


def chat(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    schema: dict | None = None,
    think: bool = False,
    num_ctx: int | None = None,
    timeout: float | None = None,
    ollama_client: ollama.Client | None = None,
    http_client: httpx.Client | None = None,
) -> Resposta:
    """Uma rodada de chat, determinística (temperature 0). Falhas viram erro de dependência."""
    timeout = timeout or settings.ollama_timeout
    with dependency_errors(_NOMES[settings.llm_provider]):
        if settings.llm_provider == "ollama":
            return _ollama(
                settings, messages, max_tokens, schema, think, num_ctx, timeout, ollama_client
            )
        return _nuvem(settings, messages, max_tokens, schema, timeout, http_client)


def _ollama(settings, messages, max_tokens, schema, think, num_ctx, timeout, client):
    owned = client is None
    client = client or ollama.Client(host=str(settings.ollama_url), timeout=timeout)
    try:
        response = client.chat(
            model=settings.generation_model,
            messages=messages,
            stream=False,
            think=think,
            format=schema,
            options={
                "num_ctx": num_ctx or settings.num_ctx,
                "num_predict": max_tokens,
                "temperature": 0,
                "seed": 42,
            },
        )
    finally:
        if owned:
            client.close()
    return Resposta(response.message.content or "", response.prompt_eval_count, response.eval_count)


def _nuvem(settings, messages, max_tokens, schema, timeout, client):
    provedor = settings.llm_provider
    corpo = {
        "model": settings.generation_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if schema is not None and provedor == "google":
        corpo["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "resposta", "schema": schema},
        }
    elif schema is not None:
        # DeepSeek só garante JSON válido; o schema vai no prompt e o Pydantic valida depois.
        corpo["response_format"] = {"type": "json_object"}
        corpo["messages"] = _schema_no_sistema(messages, schema)
    owned = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        response = client.post(
            getattr(settings, f"{provedor}_base_url").rstrip("/") + "/chat/completions",
            headers={
                "Authorization": "Bearer "
                + getattr(settings, f"{provedor}_api_key").get_secret_value()
            },
            json=corpo,
        )
        response.raise_for_status()
        dados = response.json()
    finally:
        if owned:
            client.close()
    try:
        texto = dados["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        texto = None
    if not isinstance(texto, str) or not texto.strip():
        raise DependencyUnavailable("O modelo não retornou uma resposta utilizável.")
    usage = dados.get("usage") or {}
    return Resposta(texto, usage.get("prompt_tokens"), usage.get("completion_tokens"))


def _schema_no_sistema(messages, schema):
    instrucao = "\n\nResponda só com JSON que siga este schema: " + json.dumps(schema)
    if messages and messages[0]["role"] == "system":
        return [{**messages[0], "content": messages[0]["content"] + instrucao}, *messages[1:]]
    return [{"role": "system", "content": instrucao.strip()}, *messages]
