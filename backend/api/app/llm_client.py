"""Geração de texto pelo provedor configurado: Ollama local ou API compatível com OpenAI."""

import json
from dataclasses import dataclass
from typing import Literal, TypedDict

import httpx
import ollama

from app.config import Settings
from app.errors import DependencyUnavailable, dependency_errors
from app.prompt_management import ManagedPrompt, load_prompt, observation, update_observation

_NOMES = {"ollama": "Ollama", "google": "Google Gemini", "deepseek": "DeepSeek"}


class TextPart(TypedDict):
    type: Literal["text"]
    text: str


class ImageURL(TypedDict):
    url: str


class ImagePart(TypedDict):
    type: Literal["image_url"]
    image_url: ImageURL


@dataclass
class Resposta:
    texto: str
    tokens_in: int | None
    tokens_out: int | None


def chat(
    settings: Settings,
    messages: list[dict[str, str | list[TextPart | ImagePart]]],
    *,
    max_tokens: int,
    prompt: ManagedPrompt | None = None,
    prompt_versions: dict[str, str] | None = None,
    schema: dict | None = None,
    think: bool = False,
    num_ctx: int | None = None,
    timeout: float | None = None,
    ollama_client: ollama.Client | None = None,
    http_client: httpx.Client | None = None,
    deepseek_thinking: bool | None = None,
) -> Resposta:
    """Uma rodada de chat com temperature 0. Falhas viram erro de dependência.

    `think` liga o raciocínio no Ollama; no Google, `think=False` envia
    `reasoning_effort` (GOOGLE_REASONING_EFFORT); no DeepSeek o modelo decide.
    """
    timeout = timeout or settings.ollama_timeout
    metadata: dict = {"provider": settings.llm_provider}
    versions = dict(prompt_versions or {})
    if versions:
        metadata["prompt_versions"] = versions
    with (
        observation(
            prompt.remote.name if prompt else "llm.chat",
            as_type="generation",
            model=settings.generation_model,
            metadata=metadata,
            prompt=prompt.remote if prompt else None,
        ) as generation,
        dependency_errors(_NOMES[settings.llm_provider]),
    ):
        if settings.llm_provider == "ollama":
            response = _ollama(
                settings, messages, max_tokens, schema, think, num_ctx, timeout, ollama_client
            )
        else:
            if schema is not None:
                schema_prompt = load_prompt("transport/json-schema", schema=json.dumps(schema))
                versions["transport/json-schema"] = schema_prompt.version
                update_observation(generation, metadata={**metadata, "prompt_versions": versions})
                messages = _schema_no_sistema(messages, schema_prompt.text)
            response = _nuvem(
                settings,
                messages,
                max_tokens,
                schema,
                think,
                timeout,
                http_client,
                deepseek_thinking,
            )
        if generation is not None:
            update_observation(
                generation,
                usage_details={
                    key: value
                    for key, value in {
                        "input": response.tokens_in,
                        "output": response.tokens_out,
                    }.items()
                    if value is not None
                },
            )
        return response


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


def _nuvem(settings, messages, max_tokens, schema, think, timeout, client, deepseek_thinking):
    provedor = settings.llm_provider
    corpo = {
        "model": settings.generation_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if provedor == "google" and not think and settings.google_reasoning_effort:
        # Modelos que raciocinam por padrão gastam max_tokens nisso (ex.: gemini-3.5-flash).
        corpo["reasoning_effort"] = settings.google_reasoning_effort
    if provedor == "deepseek" and deepseek_thinking is not None:
        corpo["thinking"] = {"type": "enabled" if deepseek_thinking else "disabled"}
    if schema is not None:
        # Os schemas do Pydantic ($defs, anyOf, pattern) não passam em todo provedor:
        # pede só JSON válido, o schema vai no prompt e o Pydantic valida depois.
        corpo["response_format"] = {"type": "json_object"}
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
        if response.is_error:
            # Status sem corpo: o corpo do provedor pode ecoar o pedido.
            raise DependencyUnavailable(
                f"{_NOMES[provedor]} respondeu HTTP {response.status_code}."
            )
        dados = response.json()
    finally:
        if owned:
            client.close()
    try:
        escolha = dados["choices"][0]
        texto = escolha["message"]["content"]
    except (KeyError, IndexError, TypeError):
        escolha, texto = {}, None
    cortado = schema is not None and escolha.get("finish_reason") == "length"
    if not isinstance(texto, str) or not texto.strip() or cortado:
        raise DependencyUnavailable("O modelo não retornou uma resposta utilizável.")
    usage = dados.get("usage") or {}
    return Resposta(texto, usage.get("prompt_tokens"), usage.get("completion_tokens"))


def _schema_no_sistema(messages, instrucao):
    if messages and messages[0]["role"] == "system":
        return [{**messages[0], "content": messages[0]["content"] + instrucao}, *messages[1:]]
    return [{"role": "system", "content": instrucao.strip()}, *messages]
