from datetime import date
from uuid import uuid4

import pytest
from test_access import register


@pytest.fixture
def published(client):
    from app.legal.ingest import storage_from_settings
    from app.legal.models import Norm, NormVersion

    storage = storage_from_settings(client.app.state.settings)
    storage.initialize()
    with client.app.state.db_factory() as db:
        norm = Norm(document_key="law")
        db.add(norm)
        db.flush()
        version = NormVersion(
            document_id=norm.id,
            version_label="historical",
            title="Lei de teste",
            authority="Teste",
            norm_type="lei",
            subjects=["MEI"],
            official_url="https://example.org/law",
            checksum="a" * 64,
            metadata_hash="b" * 64,
            original_key=f"tests/{uuid4()}/original.md",
            json_key=None,
            anchors=["article-1"],
            media_type="text/markdown",
            status="ready",
            effective_from=date(2020, 1, 1),
            effective_to=date(2021, 1, 1),
        )
        db.add(version)
        db.commit()
        storage.put(version.original_key, b"Art. 1 Test", "text/markdown", False)
        yield norm.id, version.id


def test_historical_citation_keeps_version(client, published):
    register(client)
    doc, version = published
    response = client.get(
        "/citacoes/resolver",
        params={"document_id": str(doc), "version_id": str(version), "anchor_id": "article-1"},
    )
    assert response.status_code == 200
    assert response.json()["version_id"] == str(version)
    assert response.json()["historical"] is True
    assert response.json()["state"] == "anchor_unavailable"  # original only; no JSON
    assert response.json()["original_url"]


def test_missing_version_offers_official_source(client, published):
    register(client)
    doc, _ = published
    response = client.get(f"/normas/{doc}/versoes/{uuid4()}")
    assert response.status_code == 200
    assert response.json()["state"] == "version_unavailable"
    assert response.json()["official_url"] == "https://example.org/law"
    assert response.json()["json_url"] is None


def test_search_filters_and_unknown_validity(client, published):
    register(client)
    assert len(client.get("/normas", params={"q": "teste", "subject": "MEI"}).json()["items"]) == 1
    assert client.get("/normas", params={"authority": "other"}).json()["items"] == []
    assert client.get("/normas", params={"effective_on": "2026-11-10"}).json()["items"] == []
    from app.legal.models import NormVersion

    with client.app.state.db_factory() as db:
        version = db.get(NormVersion, published[1])
        version.effective_from = None
        version.effective_to = None
        db.commit()
    assert client.get("/normas", params={"effective_on": "2020-06-01"}).json()["items"] == []


def test_subject_filter_is_exact(client, published):
    register(client)
    assert client.get("/normas", params={"subject": "ME"}).json()["items"] == []


def test_reader_exact_anchor_and_missing_anchor(client, published):
    register(client)
    from app.legal.ingest import storage_from_settings
    from app.legal.models import NormVersion

    storage = storage_from_settings(client.app.state.settings)
    with client.app.state.db_factory() as db:
        version = db.get(NormVersion, published[1])
        version.json_key = version.original_key + ".json"
        storage.put(
            version.json_key,
            b'{"schema_version":1,"sections":[{"anchor_id":"article-1","text":"Art. 1 Test"}]}',
            "application/json",
            False,
        )
        db.commit()
    params = {
        "document_id": str(published[0]),
        "version_id": str(published[1]),
        "anchor_id": "article-1",
    }
    response = client.get("/citacoes/resolver", params=params).json()
    assert response.get("state") == "exact", response
    assert response["anchor_id"] == "article-1"
    import httpx

    assert httpx.get(response["json_url"]).status_code == 200
    params["anchor_id"] = "missing"
    fallback = client.get("/citacoes/resolver", params=params).json()
    assert fallback["state"] == "anchor_unavailable"
    assert fallback["version_id"] == str(published[1])
    assert fallback["original_url"]


def test_catalog_full_text_search_uses_indexed_content(client, published):
    register(client)
    from app.legal.models import NormVersion
    from sqlalchemy import func

    with client.app.state.db_factory() as db:
        version = db.get(NormVersion, published[1])
        version.search_vector = func.to_tsvector(
            "simple", "Artigo sobre regularizacao extraordinaria"
        )
        db.commit()
    assert len(client.get("/normas", params={"q": "extraordinaria"}).json()["items"]) == 1
    assert client.get("/normas", params={"q": "inexistente"}).json()["items"] == []


def test_reader_cors_is_configured_from_application(client, published):
    import httpx

    response = httpx.options(
        "http://localhost:19000/legal/test.json",
        headers={"Origin": "http://testserver", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://testserver"
