import httpx
import ollama
import pytest
from app.config import Settings
from app.models import LocalModels
from app.rag import RagService
from app.vector_store import VectorStore
from qdrant_client import QdrantClient


@pytest.fixture
def service():
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"model": "qwen3:8b"},
                        {"model": "qwen3-embedding:0.6b"},
                    ]
                },
            )
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[1.0] + [0.0] * 1023]})
        if request.url.path == "/api/chat":
            return httpx.Response(
                200, json={"message": {"role": "assistant", "content": "Orientação [1]"}}
            )
        pytest.fail(f"Unexpected Ollama request: {request.url.path}")

    settings = Settings()
    store = VectorStore(settings, QdrantClient(":memory:"))
    models = LocalModels(
        settings, ollama.Client(host="http://ollama.test", transport=httpx.MockTransport(handler))
    )
    service = RagService(settings, store, models)
    store.ensure_collection()
    yield service
    service.close()


@pytest.fixture(autouse=True)
def _sem_telemetria_no_banco(request, monkeypatch):
    """Fora de tests/mvp não há Postgres: evita a gravação de telemetria em /rag/query."""
    if "mvp" not in request.node.nodeid:
        monkeypatch.setattr("app.main.registrar", lambda *args: None)


@pytest.fixture(autouse=True)
def _langfuse_offline(request, monkeypatch):
    import json
    from contextlib import nullcontext
    from pathlib import Path
    from types import SimpleNamespace

    from langfuse.model import TextPromptClient

    if "test_multiagent_real.py" in request.node.nodeid:
        return
    catalog = json.loads((Path(__file__).resolve().parents[1] / "prompt_catalog.json").read_text())

    def get_prompt(name, **_):
        return TextPromptClient(
            SimpleNamespace(
                name=name,
                version=1,
                prompt=catalog[name],
                labels=["production"],
                config={},
                tags=[],
                commit_message=None,
            )
        )

    sdk = SimpleNamespace(
        get_prompt=get_prompt,
        start_as_current_observation=lambda **_: nullcontext(),
        flush=lambda: None,
    )
    monkeypatch.setattr("app.prompt_management.client", lambda: sdk)
