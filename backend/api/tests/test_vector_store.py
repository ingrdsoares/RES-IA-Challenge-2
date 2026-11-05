import httpx
import pytest
from app.config import Settings
from app.errors import CollectionIncompatible, DependencyTimeout
from app.vector_store import VectorStore
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse


@pytest.fixture
def client():
    client = QdrantClient(":memory:")
    try:
        yield client
    finally:
        client.close()


def test_collection_is_created_empty_and_preserved(client):
    store = VectorStore(Settings(), client)
    store.ensure_collection()
    assert store.count() == 0
    client.upsert(
        "knowledge_base",
        [
            models.PointStruct(
                id=1,
                vector=[1.0] + [0.0] * 1023,
                payload={"text": "Documento de teste", "source": "Manual de teste"},
            )
        ],
    )
    store.ensure_collection()
    assert store.count() == 1


@pytest.mark.parametrize(
    "vectors",
    [
        models.VectorParams(size=512, distance=models.Distance.COSINE),
        models.VectorParams(size=1024, distance=models.Distance.DOT),
        {"named": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
    ],
)
def test_incompatible_collection_is_not_recreated(client, vectors):
    client.create_collection("knowledge_base", vectors_config=vectors)
    before = client.get_collection("knowledge_base").config.params.vectors
    with pytest.raises(CollectionIncompatible):
        VectorStore(Settings(), client).ensure_collection()
    assert client.get_collection("knowledge_base").config.params.vectors == before


def test_creation_race_revalidates_existing_collection(client, monkeypatch):
    original = client.create_collection

    def concurrent_create(*args, **kwargs):
        original(*args, **kwargs)
        raise UnexpectedResponse(409, "Conflict", b"exists", httpx.Headers())

    monkeypatch.setattr(client, "create_collection", concurrent_create)
    store = VectorStore(Settings(), client)
    store.ensure_collection()
    assert store.count() == 0


def test_search_discards_bad_payloads_and_applies_threshold_and_limit(client):
    store = VectorStore(Settings(top_k=5), client)
    store.ensure_collection()
    payloads = [
        {"text": "Trecho válido", "source": "Manual", "reference_date": "2026-11-05"},
        {"text": "Sem referência"},
        {"text": " ", "source": "Manual"},
        {"text": "Data inválida", "source": "Manual", "effective_date": "ontem"},
        {"text": "Irrelevante", "source": "Manual"},
    ]
    client.upsert(
        "knowledge_base",
        [
            models.PointStruct(
                id=i + 1,
                vector=([1.0] + [0.0] * 1023 if i < 4 else [0.0, 1.0] + [0.0] * 1022),
                payload=payload,
            )
            for i, payload in enumerate(payloads)
        ],
    )
    sources = store.search([1.0] + [0.0] * 1023)
    assert len(sources) == 1
    assert sources[0].id == 1
    assert sources[0].text == "Trecho válido"
    assert sources[0].reference_date.isoformat() == "2026-11-05"


def test_qdrant_timeout_is_translated(client, monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("internal address")

    monkeypatch.setattr(client, "collection_exists", timeout)
    with pytest.raises(DependencyTimeout):
        VectorStore(Settings(), client).ensure_collection()


@pytest.mark.parametrize("field", ["reference_date", "effective_date"])
@pytest.mark.parametrize("value", [0, "1735689600", "20261105", True, "2026-11-05T00:00:00"])
def test_non_iso_date_payload_is_discarded_before_generation(client, field, value):
    store = VectorStore(Settings(), client)
    store.ensure_collection()
    vector = [1.0] + [0.0] * 1023
    client.upsert(
        "knowledge_base",
        [
            models.PointStruct(
                id=1,
                vector=vector,
                payload={"text": "Trecho", "source": "Manual", field: value},
            )
        ],
    )
    assert store.search(vector) == []
