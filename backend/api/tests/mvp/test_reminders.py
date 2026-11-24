from datetime import UTC, date, datetime, timedelta

import pytest
from app.access import mail
from app.config import Settings
from app.jobs.models import Operation
from app.jobs.worker import execute
from app.reminders import service
from sqlalchemy import select
from test_access import csrf, register
from test_companies import DATA
from test_edit_records import create, link_evidence

TODAY = date(2026, 11, 24)
NOON = datetime(2026, 11, 24, 15, 0, tzinfo=UTC)  # 12h em Brasília
MAIL = Settings(smtp_host="mailpit", smtp_starttls=False, smtp_from="acesso@example.test")


@pytest.fixture
def company(client):
    client.app.state.settings = client.app.state.settings.model_copy(
        update={
            "smtp_host": MAIL.smtp_host,
            "smtp_starttls": False,
            "smtp_from": MAIL.smtp_from,
            "frontend_url": MAIL.frontend_url,
        }
    )
    register(client)
    return client.post("/empresas", json=DATA, headers=csrf(client)).json()


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(
        mail, "deliver", lambda settings, to, subject, body: sent.append((to, body))
    )
    monkeypatch.setattr(service, "Settings", lambda: MAIL)
    monkeypatch.setattr(service, "today", lambda: TODAY)
    return sent


def enable(client, value=True):
    return client.patch(
        "/auth/preferences", json={"reminders_enabled": value}, headers=csrf(client)
    )


def task(client, company, days, title="Pagar guia"):
    due = (TODAY + timedelta(days=days)).isoformat()
    return create(client, company, "tarefas", {"title": title, "due_date": due})


def schedule(client, now=NOON):
    with client.app.state.db_factory.begin() as db:
        return service.schedule(db, MAIL, now)


def run(client):
    factory = client.app.state.db_factory
    with factory() as db:
        ids = [
            row.id for row in db.scalars(select(Operation).where(Operation.kind == "reminder.send"))
        ]
    for operation_id in ids:
        execute(factory, operation_id, {"reminder.send": service.send})


def statuses(client):
    with client.app.state.db_factory() as db:
        return [
            row.status
            for row in db.scalars(select(Operation).where(Operation.kind == "reminder.send"))
        ]


def test_reminders_are_off_by_default(client, company, outbox):
    assert client.get("/auth/session").json()["reminders_enabled"] is False
    task(client, company, 1)
    assert schedule(client) == 0


def test_preference_is_saved_and_can_be_turned_off(client, company):
    assert enable(client).json()["reminders_enabled"] is True
    assert client.get("/auth/session").json()["reminders_enabled"] is True
    assert enable(client, False).json()["reminders_enabled"] is False


def test_preference_validates_input(client, company):
    for data in (
        {},
        {"reminders_enabled": None},
        {"reminders_enabled": "sim"},
        {"email": "a@b.co"},
    ):
        response = client.patch("/auth/preferences", json=data, headers=csrf(client))
        assert response.status_code == 422, data
    assert client.patch("/auth/preferences", json={"reminders_enabled": True}).status_code == 403


def test_cannot_enable_without_mail_server(client, company):
    client.app.state.settings = client.app.state.settings.model_copy(update={"smtp_host": ""})
    assert enable(client).status_code == 503
    assert enable(client, False).status_code == 200


@pytest.mark.parametrize("days", [0, 1, 7])
def test_reminder_is_sent_on_the_expected_days(client, company, outbox, days):
    enable(client)
    task(client, company, days)
    assert schedule(client) == 1
    run(client)
    ((to, body),) = outbox
    assert to == "person@example.com"
    due = TODAY + timedelta(days=days)
    assert f"{due:%d/%m/%Y}: 1 item" in body


@pytest.mark.parametrize("days", [-1, 2, 6, 8])
def test_other_days_send_nothing(client, company, outbox, days):
    enable(client)
    task(client, company, days)
    assert schedule(client) == 0


def test_message_has_no_user_text_nor_cnpj(client, company, outbox):
    enable(client)
    task(client, company, 1, "Segredo comercial http://golpe.example")
    task(client, company, 1, "Outro texto")
    schedule(client)
    run(client)
    ((_, body),) = outbox
    assert "Segredo" not in body and "golpe" not in body and DATA["cnpj"] not in body
    assert "25/11/2026: 2 itens" in body
    assert "http://localhost:3000/#tarefas" in body


def test_only_pending_items_count(client, company, outbox):
    enable(client)
    done = task(client, company, 1)
    headers = {**csrf(client), "Idempotency-Key": "done"}
    client.patch(f"/tarefas/{done['id']}", json={"completed": True}, headers=headers)
    due = (TODAY + timedelta(days=1)).isoformat()
    paid = create(client, company, "obrigacoes", {"name": "DAS", "due_date": due})
    link_evidence(client, company, paid)
    assert schedule(client) == 0
    create(client, company, "obrigacoes", {"name": "DASN", "due_date": due})
    assert schedule(client) == 1
    run(client)
    assert "25/11/2026: 1 item" in outbox[0][1]


def test_one_message_per_day(client, company, outbox):
    enable(client)
    task(client, company, 1)
    assert schedule(client) == 1
    assert schedule(client) == 0
    run(client)
    assert schedule(client, NOON + timedelta(hours=3)) == 0
    run(client)
    assert len(outbox) == 1


def test_quiet_hours_use_brasilia_time(client, company, outbox):
    enable(client)
    task(client, company, 1)
    assert schedule(client, datetime(2026, 11, 24, 10, 59, tzinfo=UTC)) == 0  # 7h59
    assert schedule(client, datetime(2026, 11, 25, 0, 0, tzinfo=UTC)) == 0  # 21h do dia 24
    assert schedule(client, datetime(2026, 11, 24, 11, 0, tzinfo=UTC)) == 1  # 8h


def test_disabled_after_scheduling_is_not_sent(client, company, outbox):
    enable(client)
    task(client, company, 1)
    schedule(client)
    enable(client, False)
    run(client)
    assert outbox == []
    assert statuses(client) == ["succeeded"]


def test_delivery_failure_is_retried(client, company, outbox, monkeypatch):
    enable(client)
    task(client, company, 1)
    schedule(client)

    def broken(*args):
        raise OSError("smtp fora")

    monkeypatch.setattr(mail, "deliver", broken)
    run(client)
    assert statuses(client) == ["queued"]
    monkeypatch.setattr(mail, "deliver", lambda s, to, subject, body: outbox.append((to, body)))
    run(client)
    assert statuses(client) == ["succeeded"] and len(outbox) == 1


def test_nothing_is_scheduled_without_mail_server(client, company, outbox):
    enable(client)
    task(client, company, 1)
    with client.app.state.db_factory.begin() as db:
        assert service.schedule(db, Settings(), NOON) == 0


def test_other_accounts_items_are_not_counted(client, company, outbox):
    task(client, company, 1)
    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    enable(client)
    assert schedule(client) == 0


def test_exhausted_delivery_is_retried_on_next_pass(client, company, outbox, monkeypatch):
    enable(client)
    task(client, company, 1)
    schedule(client)

    def broken(*args):
        raise OSError("smtp fora")

    monkeypatch.setattr(mail, "deliver", broken)
    for _ in range(4):
        run(client)
    assert statuses(client) == ["failed"]
    assert schedule(client, NOON + timedelta(hours=1)) == 1
    assert statuses(client) == ["queued"]


def test_stale_reminder_is_not_sent_on_another_day(client, company, outbox, monkeypatch):
    enable(client)
    task(client, company, 1)
    schedule(client)
    monkeypatch.setattr(service, "today", lambda: TODAY + timedelta(days=1))
    run(client)
    assert outbox == []
