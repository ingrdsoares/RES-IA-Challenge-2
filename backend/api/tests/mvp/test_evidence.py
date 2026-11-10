from test_access import csrf
from test_conversations import conversation


def test_declared_guide_does_not_confirm_payment(client):
    company, _ = conversation(client)
    base = "/empresas/" + company["id"]
    obligation = client.post(
        base + "/obrigacoes", json={"name": "DAS", "period": "2026-10"}, headers=csrf(client)
    )
    assert obligation.status_code == 201
    response = client.post(
        base + "/evidencias",
        json={
            "kind": "guide",
            "scope": "obligations",
            "period": "2026-10",
            "obligation_id": obligation.json()["id"],
        },
        headers={**csrf(client), "Idempotency-Key": "guide"},
    )
    assert response.status_code == 201
    assert response.json()["origin"] == "declared"
    panel = client.get(base + "/situacao-fiscal").json()
    assert panel["obligations"]["verification"] == "unverified"
    assert panel["registration"]["verification"] == "unverified"
    assert panel["coverage"] == "partial"


def test_fake_file_rejected(client):
    company, _ = conversation(client)
    evidence = client.post(
        "/empresas/" + company["id"] + "/evidencias",
        json={"kind": "guide", "scope": "obligations"},
        headers={**csrf(client), "Idempotency-Key": "upload"},
    ).json()
    response = client.put(
        "/evidencias/" + evidence["id"] + "/arquivo",
        content=b"not a pdf",
        headers={**csrf(client), "Content-Type": "application/pdf"},
    )
    assert response.status_code == 422
    assert client.get("/evidencias/" + evidence["id"] + "/arquivo").status_code == 404


def test_private_download_is_owner_scoped(client):
    company, _ = conversation(client)
    evidence = client.post(
        "/empresas/" + company["id"] + "/evidencias",
        json={"kind": "guide", "scope": "obligations"},
        headers={**csrf(client), "Idempotency-Key": "upload"},
    ).json()
    body = b"%PDF-1.4\n demo content"
    assert (
        client.put(
            "/evidencias/" + evidence["id"] + "/arquivo",
            content=body,
            headers={**csrf(client), "Content-Type": "application/pdf"},
        ).status_code
        == 200
    )
    import httpx

    assert (
        httpx.get(client.get("/evidencias/" + evidence["id"] + "/arquivo").json()["url"]).content
        == body
    )
    client.post("/auth/logout", headers=csrf(client))
    from test_access import register

    register(client, "other@example.com")
    assert client.get("/evidencias/" + evidence["id"] + "/arquivo").status_code == 404


def test_large_upload_rejected_and_expired_evidence_preserved(client):
    company, _ = conversation(client)
    base = "/empresas/" + company["id"]
    evidence = client.post(
        base + "/evidencias",
        json={"kind": "certificate", "scope": "federal_certificate", "valid_until": "2020-01-01"},
        headers={**csrf(client), "Idempotency-Key": "expired"},
    ).json()
    assert (
        client.put(
            "/evidencias/" + evidence["id"] + "/arquivo",
            content=b"%PDF-" + b"x" * (10 * 1024 * 1024),
            headers={**csrf(client), "Content-Type": "application/pdf"},
        ).status_code
        == 413
    )
    assert client.get("/evidencias/" + evidence["id"] + "/arquivo").status_code == 404
    panel = client.get(base + "/situacao-fiscal").json()["federal_certificate"]
    assert panel["evidence_state"] == "expired"
    assert panel["verification"] == "unverified"
    assert panel["latest_evidence"]["id"] == evidence["id"]


def test_cannot_link_other_profile_obligation(client):
    from test_companies import DATA

    company, _ = conversation(client)
    other = client.post(
        "/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client)
    ).json()
    obligation = client.post(
        "/empresas/" + other["id"] + "/obrigacoes", json={"name": "DAS"}, headers=csrf(client)
    ).json()
    assert (
        client.post(
            "/empresas/" + company["id"] + "/evidencias",
            json={"kind": "guide", "scope": "obligations", "obligation_id": obligation["id"]},
            headers={**csrf(client), "Idempotency-Key": "cross"},
        ).status_code
        == 404
    )


def test_storage_failure_does_not_publish_attachment(client, monkeypatch):
    from app.storage import ObjectStorage
    from botocore.exceptions import EndpointConnectionError

    company, _ = conversation(client)
    evidence = client.post(
        "/empresas/" + company["id"] + "/evidencias",
        json={"kind": "guide", "scope": "obligations"},
        headers={**csrf(client), "Idempotency-Key": "interrupted"},
    ).json()

    def fail(*args, **kwargs):
        raise EndpointConnectionError(endpoint_url="http://unavailable.invalid")

    monkeypatch.setattr(ObjectStorage, "put", fail)
    assert (
        client.put(
            "/evidencias/" + evidence["id"] + "/arquivo",
            content=b"%PDF-1.4 test",
            headers={**csrf(client), "Content-Type": "application/pdf"},
        ).status_code
        == 503
    )
    assert client.get("/evidencias/" + evidence["id"] + "/arquivo").status_code == 404
