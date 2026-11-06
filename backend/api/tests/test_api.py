import pytest
from app.errors import CollectionIncompatible, DependencyTimeout, DependencyUnavailable, QueryBusy
from app.main import app, create_app
from fastapi.testclient import TestClient
from qdrant_client import models

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("question", ["", "  ", "x" * 2001])
def test_invalid_question_returns_422(service, question):
    with TestClient(create_app(service=service)) as client:
        assert client.post("/rag/query", json={"question": question}).status_code == 422


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


@pytest.mark.parametrize(
    "error", [DependencyUnavailable("missing model"), DependencyTimeout("timeout")]
)
def test_readiness_requires_models_even_with_empty_collection(service, monkeypatch, error):
    def fail():
        raise error

    monkeypatch.setattr(service.models, "check_models", fail)
    with TestClient(create_app(service=service)) as client:
        assert client.get("/ready").status_code == 503


def test_http_response_includes_generated_answer_and_context_references(service):
    service.store.client.upsert(
        "knowledge_base",
        [
            models.PointStruct(
                id=7,
                vector=[1.0] + [0.0] * 1023,
                payload={
                    "text": "Documento técnico de teste",
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
        assert body["sources"][0]["id"] == 7
        assert body["sources"][0]["source"] == "Manual"
        assert body["sources"][0]["effective_date"] == "2026-11-05"
