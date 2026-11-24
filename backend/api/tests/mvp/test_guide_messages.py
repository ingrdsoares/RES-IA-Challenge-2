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
    assert (
        post_message(client, chat, "disabled", text="Veja a guia", evidence_id=guide).status_code
        == 503
    )
    enable(client, monkeypatch)
    other = client.post(
        "/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client)
    ).json()
    foreign = attach(client, other, "foreign", "image/png", PNG)
    for key, evidence, status in [
        ("foreign", foreign, 404),
        ("missing", missing, 404),
        ("pdf", pdf, 422),
    ]:
        assert (
            post_message(client, chat, key, text="Veja a guia", evidence_id=evidence).status_code
            == status
        )
    assert client.get(f"/conversas/{chat['id']}/mensagens").json()["items"] == []

    response = post_message(client, chat, "own", text="Qual a competência?", evidence_id=guide)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert (
        post_message(
            client,
            chat,
            "replace",
            text="Confirmo",
            evidence_id=guide,
            confirmation_for=response.json()["operation_id"],
            confirmation={"period": "2026-10"},
        ).status_code
        == 422
    )

    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    assert client.get(f"/empresas/{company['id']}/guias-para-assistente").status_code == 404


def run_guide(client, submitted, model):
    from uuid import UUID

    from app.assistant.agents.executor import execute_run

    execute_run(
        client.app.state.db_factory,
        UUID(submitted["operation_id"]),
        model=model,
        settings=client.app.state.settings,
    )
    return client.get(submitted["status_url"]).json()


def mock_reading(monkeypatch, fields, calls):
    from app.assistant.agents import executor
    from app.assistant.agents.guide_vision import GuideReading

    def read(settings, image, media_type, *, timeout):
        assert media_type == "image/png"
        assert image == PNG
        calls.append("document")
        return GuideReading.model_validate(fields), {"model": "deepseek-flash"}

    monkeypatch.setattr(executor, "read_guide", read, raising=False)


class GuideOnly:
    def generate(self, role, schema, payload, timeout, output_tokens):
        assert role == "plan"
        assert "guide_reading" in payload["context"]
        return schema(intent="Ler guia", agents=[]), {}


def test_worker_reads_guide_before_supervisor_and_reuses_reading_after_confirmation(
    client, monkeypatch
):
    from test_multiagent_workflow import Model

    company, chat = conversation(client)
    enable(client, monkeypatch)
    guide = attach(client, company, "worker-guide", "image/png", PNG)
    calls = []
    fields = {"period": "2026-10", "due_date": "2026-11-20", "amount": "81.05"}
    mock_reading(monkeypatch, fields, calls)
    url = f"/conversas/{chat['id']}/mensagens"
    submitted = post_message(
        client, chat, "read", text="Qual a competência e o valor desta guia?", evidence_id=guide
    ).json()
    status = run_guide(client, submitted, GuideOnly())
    assert status["status"] == "succeeded"
    assert [step["name"] for step in status["run"]["stages"]] == ["document", "plan"]
    result = client.get(url).json()["items"][-1]
    assert result["context"]["guide_reading"] == {"evidence_id": guide, **fields}
    assert "data:image" not in str(result)

    class FiscalModel(Model):
        def generate(self, role, schema, payload, timeout, output_tokens):
            if role == "fiscal":
                assert payload["period"] == "2026-11"
            return super().generate(role, schema, payload, timeout, output_tokens)

    submitted = post_message(
        client,
        chat,
        "different",
        text="Paguei esta guia em 2026-11?",
        evidence_id=guide,
    ).json()
    status = run_guide(client, submitted, FiscalModel())
    assert status["status"] == "awaiting_data"
    assert status["result"]["missing_fields"] == ["period"]
    confirmed = post_message(
        client,
        chat,
        "confirm",
        text="Confirmo novembro",
        confirmation_for=submitted["operation_id"],
        confirmation={"period": "2026-11"},
    )
    assert confirmed.json()["operation_id"] == submitted["operation_id"]
    status = run_guide(client, submitted, FiscalModel())
    assert status["status"] == "succeeded"
    assert calls == ["document", "document"]
    assert sum(step["name"] == "document" for step in status["run"]["stages"]) == 1
    result = client.get(url).json()["items"][-1]["context"]
    assert result["guide_reading"] == {"evidence_id": guide, **fields}
    assert result["fiscal_status"]["obligations"]["verification"] == "unverified"


def test_worker_handles_unreadable_guide_and_rejects_wrong_signature(client, monkeypatch):
    from app.storage import ObjectStorage
    from test_multiagent_workflow import Model

    company, chat = conversation(client)
    enable(client, monkeypatch)
    guide = attach(client, company, "unreadable", "image/png", PNG)
    calls = []
    fields = {"period": None, "due_date": None, "amount": None}
    mock_reading(monkeypatch, fields, calls)
    submitted = post_message(
        client, chat, "unreadable-read", text="Qual o valor?", evidence_id=guide
    ).json()
    assert run_guide(client, submitted, GuideOnly())["status"] == "succeeded"
    result = client.get(f"/conversas/{chat['id']}/mensagens").json()["items"][-1]
    assert result["context"]["guide_reading"] == {"evidence_id": guide, **fields}
    submitted = post_message(
        client, chat, "unreadable-payment", text="Paguei a guia?", evidence_id=guide
    ).json()
    status = run_guide(client, submitted, Model())
    assert status["status"] == "awaiting_data"
    assert status["result"]["missing_fields"] == ["period"]
    post_message(
        client,
        chat,
        "confirm",
        text="Confirmo",
        confirmation_for=submitted["operation_id"],
        confirmation={"period": "2026-10"},
    )
    assert run_guide(client, submitted, Model())["status"] == "succeeded"

    monkeypatch.setattr(ObjectStorage, "get", lambda *args, **kwargs: b"%PDF-1.4")
    submitted = post_message(
        client, chat, "corrupt", text="Qual o valor?", evidence_id=guide
    ).json()
    assert run_guide(client, submitted, GuideOnly())["status"] == "failed"
    assert len(calls) == 2


def test_worker_rechecks_guide_company_before_reading(client, monkeypatch):
    from uuid import UUID

    from app.evidence.models import Evidence

    company, chat = conversation(client)
    enable(client, monkeypatch)
    guide = attach(client, company, "moved-guide", "image/png", PNG)
    other = client.post(
        "/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client)
    ).json()
    submitted = post_message(
        client, chat, "old-job", text="Qual o valor?", evidence_id=guide
    ).json()
    with client.app.state.db_factory.begin() as db:
        db.get(Evidence, UUID(guide)).company_id = UUID(other["id"])

    calls = []
    mock_reading(monkeypatch, {"period": None, "due_date": None, "amount": None}, calls)
    assert run_guide(client, submitted, GuideOnly())["status"] == "failed"
    assert calls == []
