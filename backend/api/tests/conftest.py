import httpx
import ollama
import pytest
from qdrant_client import QdrantClient

from app.config import Settings
from app.models import LocalModels
from app.rag import RagService
from app.vector_store import VectorStore


@pytest.fixture
def service():
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"model": "qwen3:8b"}, {"model": "qwen3-embedding:0.6b"},
            ]})
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[1.0] + [0.0] * 1023]})
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"role": "assistant", "content": "Orientação [1]"}})
        pytest.fail(f"Unexpected Ollama request: {request.url.path}")

    settings = Settings()
    store = VectorStore(settings, QdrantClient(":memory:"))
    models = LocalModels(settings, ollama.Client(host="http://ollama.test", transport=httpx.MockTransport(handler)))
    service = RagService(settings, store, models)
    store.ensure_collection()
    yield service
    service.close()
