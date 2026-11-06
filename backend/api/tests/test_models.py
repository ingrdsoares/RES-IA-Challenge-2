import json

import httpx
import ollama
import pytest
from app.config import Settings
from app.errors import DependencyTimeout, DependencyUnavailable
from app.models import LocalModels, prepare_sources
from app.schemas import Source


def make_models(handler, **settings):
    client = ollama.Client(host="http://ollama.test", transport=httpx.MockTransport(handler))
    return LocalModels(Settings(**settings), client)


def source(text="Trecho para responder.", **extra):
    return Source(id=1, text=text, source="Manual técnico", score=0.9, **extra)


def test_embedding_uses_retrieval_instruction_and_correct_dimension():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/embed"
        assert body["model"] == "qwen3-embedding:0.6b"
        assert body["input"] == (
            "Instruct: Given a web search query, retrieve relevant passages "
            "that answer the query\nQuery:Como funciona?"
        )
        assert body["truncate"] is False
        return httpx.Response(200, json={"embeddings": [[1.0] + [0.0] * 1023]})

    models = make_models(handler)
    try:
        assert models.embed_question("Como funciona?") == [1.0] + [0.0] * 1023
    finally:
        models.close()


@pytest.mark.parametrize("vector", [[1.0], [0.0] * 1024, ["bad"] * 1024, []])
def test_invalid_embedding_is_rejected(vector):
    models = make_models(lambda request: httpx.Response(200, json={"embeddings": [vector]}))
    with pytest.raises(DependencyUnavailable):
        models.embed_question("Pergunta")
    models.close()


def test_missing_model_is_not_downloaded():
    def handler(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"model": "qwen3:8b"}]})

    models = make_models(handler)
    with pytest.raises(DependencyUnavailable):
        models.check_models()
    models.close()


def test_both_installed_models_are_ready():
    models = make_models(
        lambda request: httpx.Response(
            200,
            json={
                "models": [
                    {"model": "qwen3:8b"},
                    {"model": "qwen3-embedding:0.6b"},
                ]
            },
        )
    )
    models.check_models()
    models.close()


def test_generation_is_grounded_and_thinking_is_disabled():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert body["stream"] is False and body["think"] is False
        assert body["options"]["num_ctx"] == 8192
        assert body["options"]["num_predict"] == 1024
        assert body["messages"][0]["role"] == "system"
        assert "instruções" in body["messages"][0]["content"]
        assert "Trecho para responder." in body["messages"][1]["content"]
        assert "[1]" in body["messages"][1]["content"]
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": "Resposta [1]"}}
        )

    models = make_models(handler)
    assert models.answer("Pergunta", [source()]) == "Resposta [1]"
    models.close()


@pytest.mark.parametrize("body", [{"message": {"role": "assistant", "content": " "}}, {}])
def test_empty_generation_is_dependency_failure(body):
    models = make_models(lambda request: httpx.Response(200, json=body))
    with pytest.raises(DependencyUnavailable):
        models.answer("Pergunta", [source()])
    models.close()


def test_ollama_timeout_is_translated():
    def handler(request):
        raise httpx.ReadTimeout("private endpoint", request=request)

    models = make_models(handler)
    with pytest.raises(DependencyTimeout):
        models.embed_question("Pergunta")
    models.close()


def test_prepare_sources_truncates_without_mutating_original():
    sources = [source("A" * 8), source("B" * 8).model_copy(update={"id": 2})]
    selected = prepare_sources(sources, 12)
    assert [s.text for s in selected] == ["A" * 8, "B" * 4]
    assert sources[1].text == "B" * 8


def test_oversized_prompt_is_rejected_before_calling_ollama():
    def handler(request):
        pytest.fail("Oversized prompt must not reach Ollama")

    models = make_models(handler)
    with pytest.raises(DependencyUnavailable):
        models.answer("Pergunta", [source("🎉" * 6000)])
    models.close()


def test_ollama_http_error_is_translated():
    models = make_models(lambda request: httpx.Response(404, json={"error": "private model path"}))
    with pytest.raises(DependencyUnavailable):
        models.embed_question("Pergunta")
    models.close()


def test_nonfinite_embedding_is_rejected():
    class InvalidClient:
        def embed(self, **kwargs):
            return ollama.EmbedResponse(embeddings=[[float("nan")] + [0.0] * 1023])

    with pytest.raises(DependencyUnavailable):
        LocalModels(Settings(), InvalidClient()).embed_question("Pergunta")


def test_unicode_context_is_trimmed_to_fit_prompt_budget():
    selected = prepare_sources([source("🎉" * 6000)], 6000, question="Pergunta")
    assert len(selected) == 1
    assert 0 < len(selected[0].text) < 2000

    models = make_models(
        lambda request: httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Resposta [1]"}},
        )
    )
    assert models.answer("Pergunta", selected) == "Resposta [1]"
    models.close()
