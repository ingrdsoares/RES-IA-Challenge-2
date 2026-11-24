import pytest
from app.dependencies import require_account
from app.errors import CollectionIncompatible, DependencyTimeout, DependencyUnavailable, QueryBusy
from app.main import app
from app.main import create_app as original_create_app
from fastapi.testclient import TestClient
from qdrant_client import models


def create_app(**kwargs):
    application = original_create_app(**kwargs)
    application.dependency_overrides[require_account] = lambda: object()
    return application


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version():
    r = client.get("/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "commit_sha" in data
    assert "environment" in data
    assert "build_timestamp" in data


def test_invalid_question_returns_422(service):
    with TestClient(create_app(service=service)) as client:
        assert client.post("/rag/query", json={"question": ""}).status_code == 422


def test_empty_base_is_a_valid_response(service):
    with TestClient(create_app(service=service)) as client:
        assert client.get("/ready").json() == {"status": "ready"}
        response = client.post("/rag/query", json={"question": "Como funciona?"})
        assert response.status_code == 200
        assert response.json()["status"] == "empty_knowledge_base"
        assert response.json()["sources"] == []


@pytest.mark.parametrize(
    "error, status",
    [
        (DependencyUnavailable("private-host"), 503),
        (DependencyTimeout("private-host"), 504),
        (CollectionIncompatible("private-host"), 503),
        (QueryBusy(), 503),
    ],
)
def test_dependency_errors_are_explicit_and_do_not_leak_details(
    service, monkeypatch, error, status
):
    def fail(question):
        raise error

    monkeypatch.setattr(service, "query", fail)
    with TestClient(create_app(service=service)) as client:
        response = client.post("/rag/query", json={"question": "Pergunta"})
        assert response.status_code == status
        assert "private-host" not in response.text


def test_startup_failure_keeps_health_and_allows_recovery(service, monkeypatch):
    original = service.store.ensure_collection

    def unavailable():
        raise DependencyUnavailable("Offline")

    monkeypatch.setattr(service.store, "ensure_collection", unavailable)
    with TestClient(create_app(service=service)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.post("/rag/query", json={"question": "Pergunta"}).status_code == 503
        monkeypatch.setattr(service.store, "ensure_collection", original)
        assert client.get("/ready").status_code == 200
        assert client.post("/rag/query", json={"question": "Pergunta"}).status_code == 200


def test_readiness_requires_models_even_with_empty_collection(service, monkeypatch):
    def fail():
        raise DependencyUnavailable("missing model")

    monkeypatch.setattr(service.models, "check_models", fail)
    with TestClient(create_app(service=service)) as client:
        assert client.get("/ready").status_code == 503


def test_http_response_includes_generated_answer_and_context_references(service):
    document_text = "Documento técnico de teste " + "🎉" * 30000
    service.store.client.upsert(
        "knowledge_base",
        [
            models.PointStruct(
                id=7,
                vector={"dense": [1.0] + [0.0] * 1023},
                payload={
                    "text": document_text,
                    "source": "Manual",
                    "effective_date": "2026-11-05",
                },
            )
        ],
    )
    with TestClient(create_app(service=service)) as client:
        response = client.post("/rag/query", json={"question": "Pergunta"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "answered"
        assert body["answer"] == "Orientação [1]"
        source = body["sources"][0]
        assert source["id"] == 7
        assert source["source"] == "Manual"
        assert source["effective_date"] == "2026-11-05"
        context = source["text"]
        assert 0 < len(context) < len(document_text)
        assert document_text.startswith(context)
        assert len(context.encode("utf-8")) <= 2 * (
            service.settings.num_ctx - service.settings.num_predict - 256
        )
