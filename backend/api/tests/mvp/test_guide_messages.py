from test_access import csrf, register
from test_companies import DATA
from test_conversations import conversation

PNG = b"\x89PNG\r\n\x1a\nfixture"
JPEG = b"\xff\xd8\xfffixture"


def attach(client, company, key, media_type=None, content=None):
    response = client.post(
        f"/empresas/{company['id']}/evidencias",
        json={"kind": "guide", "scope": "obligations", "period": "2026-10"},
        headers={**csrf(client), "Idempotency-Key": key},
    )
    assert response.status_code == 201
    item = response.json()
    if media_type:
        response = client.put(
            f"/evidencias/{item['id']}/arquivo",
            content=content,
            headers={**csrf(client), "Content-Type": media_type},
        )
        assert response.status_code == 200
    return item["id"]


def enable(client, monkeypatch):
    from pydantic import SecretStr

    settings = client.app.state.settings
    monkeypatch.setattr(settings, "guide_vision_enabled", True)
    monkeypatch.setattr(settings, "deepseek_api_key", SecretStr("test-key"))


def post_message(client, chat, key, **payload):
    return client.post(
        f"/conversas/{chat['id']}/mensagens",
        json=payload,
        headers={**csrf(client), "Idempotency-Key": key},
    )


def test_guide_options_include_existing_png_and_jpeg_only(client, monkeypatch):
    company, _ = conversation(client)
    url = f"/empresas/{company['id']}/guias-para-assistente"
    assert client.get(url).json() == {"enabled": False, "items": [], "next_cursor": None}
    enable(client, monkeypatch)
    png = attach(client, company, "png", "image/png", PNG)
    jpeg = attach(client, company, "jpeg", "image/jpeg", JPEG)
    attach(client, company, "pdf", "application/pdf", b"%PDF-1.4")
    attach(client, company, "missing")
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert {item["id"] for item in response.json()["items"]} == {png, jpeg}
    assert set(response.json()["items"][0]) == {"id", "period", "created_at"}


def test_rejects_foreign_or_unavailable_guide(client, monkeypatch):
    company, chat = conversation(client)
    guide = attach(client, company, "own", "image/png", PNG)
    missing = attach(client, company, "missing")
    pdf = attach(client, company, "pdf", "application/pdf", b"%PDF-1.4")
    assert post_message(client, chat, "disabled", text="Veja a guia", evidence_id=guide).status_code == 503
    enable(client, monkeypatch)
    other = client.post(
        "/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client)
    ).json()
    foreign = attach(client, other, "foreign", "image/png", PNG)
    for key, evidence, status in [("foreign", foreign, 404), ("missing", missing, 404), ("pdf", pdf, 422)]:
        assert post_message(client, chat, key, text="Veja a guia", evidence_id=evidence).status_code == status
    assert client.get(f"/conversas/{chat['id']}/mensagens").json()["items"] == []

    response = post_message(client, chat, "own", text="Qual a competência?", evidence_id=guide)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert post_message(
        client, chat, "replace", text="Confirmo", evidence_id=guide,
        confirmation_for=response.json()["operation_id"], confirmation={"period": "2026-10"},
    ).status_code == 422

    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    assert client.get(f"/empresas/{company['id']}/guias-para-assistente").status_code == 404
