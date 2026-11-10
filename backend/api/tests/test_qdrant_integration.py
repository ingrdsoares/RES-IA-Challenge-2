import os
from uuid import uuid4

import pytest
from app.config import Settings
from app.vector_store import VectorStore
from qdrant_client import QdrantClient, models


@pytest.mark.integration
def test_real_qdrant_search_survives_client_reconnect():
    url = os.getenv("QDRANT_TEST_URL")
    if not url:
        pytest.skip("Set QDRANT_TEST_URL to test a real Qdrant instance")
    name = f"test_rag_{uuid4().hex}"
    settings = Settings(qdrant_url=url, collection_name=name)
    client = QdrantClient(url=url, timeout=5)
    store = VectorStore(settings, client)
    created = False
    try:
        store.ensure_collection()
        created = True
        vector = [1.0] + [0.0] * 1023
        client.upsert(
            name,
            [
                models.PointStruct(
                    id=1,
                    vector={"dense": vector},
                    payload={
                        "text": "Documento sintético de teste",
                        "source": "Teste de integração",
                    },
                )
            ],
            wait=True,
        )
        assert store.search(vector)[0].text == "Documento sintético de teste"
        store.close()
        client = QdrantClient(url=url, timeout=5)
        store = VectorStore(settings, client)
        store.ensure_collection()
        assert store.count() == 1
        assert store.search(vector)[0].id == 1
    finally:
        if created:
            client.delete_collection(name)
        store.close()
