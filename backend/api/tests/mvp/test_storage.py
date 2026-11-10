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
