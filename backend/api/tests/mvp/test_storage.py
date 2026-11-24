import httpx
import pytest


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
    from app.config import Settings
    from app.legal.ingest import storage_from_settings

    endpoint = "http://localhost:19000"
    origins = ["https://reader.example.org", "http://testserver"]
    settings = Settings(
        s3_endpoint=endpoint,
        s3_public_endpoint=endpoint,
        s3_access_key="sd_test_user",
        s3_secret_key="sd_test_password",
        allowed_origins=origins,
    )
    store = storage_from_settings(settings)
    store.initialize()
    key = store.put("tests/cors.json", b"{}", "application/json", private=False)
    for origin in origins:
        response = httpx.options(
            f"{endpoint}/legal/{key}",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert response.headers["access-control-allow-origin"] == origin
    untrusted = httpx.options(
        f"{endpoint}/legal/{key}",
        headers={"Origin": "https://attacker.invalid", "Access-Control-Request-Method": "GET"},
    )
    assert untrusted.headers.get("access-control-allow-origin") != "https://attacker.invalid"
