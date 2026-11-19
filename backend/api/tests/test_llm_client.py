import json

import httpx
import ollama
import pytest
from app.config import Settings
from app.errors import DependencyTimeout, DependencyUnavailable
from app.llm_client import chat

MENSAGENS = [{"role": "system", "content": "Sistema."}, {"role": "user", "content": "Pergunta"}]
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def _nuvem(provedor, respond):
    settings = Settings(
        llm_provider=provedor, generation_model="modelo-x", **{f"{provedor}_api_key": "chave-k"}
    )
    return settings, httpx.Client(transport=httpx.MockTransport(respond))


def _resposta_openai(content="oi", usage=None):
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 7, "completion_tokens": 3},
    }


def test_ollama_envia_opcoes_atuais():
    enviados = []

    def respond(request):
        enviados.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": "resposta"},
                "done": True,
                "prompt_eval_count": 20,
                "eval_count": 10,
            },
        )

    client = ollama.Client(transport=httpx.MockTransport(respond))
    resposta = chat(
        Settings(), MENSAGENS, max_tokens=256, schema=SCHEMA, num_ctx=4096, ollama_client=client
    )
    corpo = enviados[0]
    assert corpo["options"]["temperature"] == 0
    assert corpo["options"]["seed"] == 42
    assert corpo["options"]["num_ctx"] == 4096
    assert corpo["options"]["num_predict"] == 256
    assert corpo["think"] is False
    assert corpo["format"] == SCHEMA
    assert (resposta.texto, resposta.tokens_in, resposta.tokens_out) == ("resposta", 20, 10)
    client.close()


def test_google_usa_json_object_e_bearer():
    pedidos = []

    def respond(request):
        pedidos.append(request)
        return httpx.Response(200, json=_resposta_openai('{"ok": true}'))

    settings, http = _nuvem("google", respond)
    resposta = chat(settings, MENSAGENS, max_tokens=128, schema=SCHEMA, http_client=http)
    pedido = pedidos[0]
    corpo = json.loads(pedido.content)
    assert str(pedido.url) == settings.google_base_url + "/chat/completions"
    assert pedido.headers["authorization"] == "Bearer chave-k"
    assert corpo["model"] == "modelo-x"
    assert corpo["max_tokens"] == 128
    assert corpo["temperature"] == 0
    # Gemini recusa partes do JSON Schema do Pydantic; mesmo caminho do DeepSeek.
    assert corpo["response_format"] == {"type": "json_object"}
    assert json.dumps(SCHEMA) in corpo["messages"][0]["content"]
    assert (resposta.texto, resposta.tokens_in, resposta.tokens_out) == ('{"ok": true}', 7, 3)


def test_deepseek_usa_json_object_e_schema_no_prompt():
    corpos = []

    def respond(request):
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=_resposta_openai())

    settings, http = _nuvem("deepseek", respond)
    chat(settings, MENSAGENS, max_tokens=64, schema=SCHEMA, http_client=http)
    chat(settings, MENSAGENS, max_tokens=64, http_client=http)
    com_schema, sem_schema = corpos
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert com_schema["response_format"] == {"type": "json_object"}
    sistema = com_schema["messages"][0]["content"]
    assert sistema.startswith("Sistema.") and "JSON" in sistema and json.dumps(SCHEMA) in sistema
    assert com_schema["messages"][1:] == MENSAGENS[1:]
    assert "response_format" not in sem_schema
    assert sem_schema["messages"] == MENSAGENS
    assert MENSAGENS[0]["content"] == "Sistema."


@pytest.mark.parametrize("status", [401, 429, 500])
def test_nuvem_http_erro_vira_dependencia(status):
    settings, http = _nuvem("google", lambda request: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(DependencyUnavailable) as erro:
        chat(settings, MENSAGENS, max_tokens=64, http_client=http)
    assert "chave-k" not in str(erro.value)
    assert "Google Gemini" in str(erro.value) and str(status) in str(erro.value)


def test_nuvem_timeout_vira_dependency_timeout():
    def respond(request):
        raise httpx.ReadTimeout("lento", request=request)

    settings, http = _nuvem("deepseek", respond)
    with pytest.raises(DependencyTimeout):
        chat(settings, MENSAGENS, max_tokens=64, http_client=http)


@pytest.mark.parametrize(
    "corpo",
    [
        {"choices": []},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": "  "}}]},
    ],
)
def test_nuvem_resposta_vazia(corpo):
    settings, http = _nuvem("google", lambda request: httpx.Response(200, json=corpo))
    with pytest.raises(DependencyUnavailable):
        chat(settings, MENSAGENS, max_tokens=64, http_client=http)


def test_google_desliga_raciocinio_salvo_quando_pedido_ou_configurado():
    corpos = []

    def respond(request):
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=_resposta_openai())

    settings, http = _nuvem("google", respond)
    chat(settings, MENSAGENS, max_tokens=64, http_client=http)
    chat(settings, MENSAGENS, max_tokens=64, think=True, http_client=http)
    chat(
        settings.model_copy(update={"google_reasoning_effort": ""}),
        MENSAGENS,
        max_tokens=64,
        http_client=http,
    )
    padrao, pensando, sem_campo = corpos
    assert padrao["reasoning_effort"] == "none"
    assert "reasoning_effort" not in pensando
    assert "reasoning_effort" not in sem_campo


def test_deepseek_nao_recebe_reasoning_effort():
    corpos = []

    def respond(request):
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=_resposta_openai())

    settings, http = _nuvem("deepseek", respond)
    chat(settings, MENSAGENS, max_tokens=64, http_client=http)
    assert "reasoning_effort" not in corpos[0]


def test_json_cortado_por_limite_vira_dependencia():
    corpo = {"choices": [{"message": {"content": '{"ok": tr'}, "finish_reason": "length"}]}
    settings, http = _nuvem("google", lambda request: httpx.Response(200, json=corpo))
    with pytest.raises(DependencyUnavailable):
        chat(settings, MENSAGENS, max_tokens=64, schema=SCHEMA, http_client=http)
