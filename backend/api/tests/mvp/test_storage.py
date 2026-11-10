import httpx
import pytest


def test_private_url_requires_owner(client):
    from app.storage import ObjectStorage

    store = ObjectStorage(
        endpoint="http://localhost:19000",
        public_endpoint="http://localhost:19000",
        access_key="sd_test_user",
        secret_key="sd_test_password",
    )
    store.initialize()
    key = store.put("tests/file.pdf", b"%PDF-example", "application/pdf", private=True)
    assert httpx.get("http://localhost:19000/private/" + key).status_code == 403
    response = httpx.get(store.signed_get(key, private=True))
    assert response.status_code == 200
    assert response.content == b"%PDF-example"


def test_invalid_storage_key_rejected():
    from app.storage import ObjectStorage

    store = ObjectStorage(
        endpoint="http://localhost:19000",
        public_endpoint="http://localhost:19000",
        access_key="sd_test_user",
        secret_key="sd_test_password",
    )
    with pytest.raises(ValueError):
        store.put("../outside", b"private", "text/plain", private=True)


def test_legal_reader_cors_allows_only_configured_origin():
    from app.storage import ObjectStorage

    store = ObjectStorage(
        endpoint="http://localhost:19000",
        public_endpoint="http://localhost:19000",
        access_key="sd_test_user",
        secret_key="sd_test_password",
        allowed_origins=["https://reader.example.org"],
    )
    store.initialize()
    key = store.put("tests/cors.json", b"{}", "application/json", private=False)
    response = httpx.options(
        "http://localhost:19000/legal/" + key,
        headers={"Origin": "https://reader.example.org", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "https://reader.example.org"
    untrusted = httpx.options(
        "http://localhost:19000/legal/" + key,
        headers={"Origin": "https://attacker.invalid", "Access-Control-Request-Method": "GET"},
    )
    assert untrusted.headers.get("access-control-allow-origin") != "https://attacker.invalid"
