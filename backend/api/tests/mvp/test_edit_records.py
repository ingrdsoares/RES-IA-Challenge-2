from uuid import UUID

from sqlalchemy import select
from test_access import csrf, register
from test_conversations import conversation

TASK = {"title": "Conferir guia", "period": "2026-10", "due_date": "2026-11-20"}
OBLIGATION = {"name": "DAS outubro", "period": "2026-10", "due_date": "2026-11-20"}


def create(client, company, path, data):
    response = client.post(f"/empresas/{company['id']}/{path}", json=data, headers=csrf(client))
    assert response.status_code == 201
    return response.json()


def as_other_owner(client):
    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")


def complete(client, task_id):
    headers = {**csrf(client), "Idempotency-Key": "done"}
    assert (
        client.patch(f"/tarefas/{task_id}", json={"completed": True}, headers=headers).status_code
        == 200
    )


def link_evidence(client, company, obligation, **extra):
    response = client.post(
        f"/empresas/{company['id']}/evidencias",
        json={
            "kind": "payment",
            "scope": "obligations",
            "obligation_id": obligation["id"],
            **extra,
        },
        headers={**csrf(client), "Idempotency-Key": "evidence"},
    )
    assert response.status_code == 201


def test_task_edit_replaces_fields_and_keeps_completion(client):
    company, _ = conversation(client)
    task = create(client, company, "tarefas", TASK)
    complete(client, task["id"])
    response = client.put(
        f"/tarefas/{task['id']}",
        json={"title": "Pagar guia", "period": None, "due_date": "2026-12-20"},
        headers=csrf(client),
    )
    assert response.status_code == 200
    body = client.get(f"/tarefas/{task['id']}").json()
    assert (body["title"], body["period"], body["due_date"]) == ("Pagar guia", None, "2026-12-20")
    assert body["completed"] is True


def test_task_edit_requires_title(client):
    company, _ = conversation(client)
    task = create(client, company, "tarefas", TASK)
    for title in ("", "   ", None):
        response = client.put(
            f"/tarefas/{task['id']}",
            json={"title": title, "period": None, "due_date": None},
            headers=csrf(client),
        )
        assert response.status_code == 422


def test_task_delete_removes_history_and_stored_copies(client):
    from app.jobs.models import Operation
    from app.tasks.models import TaskEvent

    company, _ = conversation(client)
    task = create(client, company, "tarefas", TASK)
    complete(client, task["id"])
    assert client.delete(f"/tarefas/{task['id']}", headers=csrf(client)).status_code == 204
    assert client.get(f"/tarefas/{task['id']}").status_code == 404
    with client.app.state.db_factory() as db:
        assert db.scalars(select(TaskEvent)).all() == []
        assert db.scalars(select(Operation).where(Operation.kind == "task.complete")).all() == []


def test_task_of_other_owner_cannot_be_changed(client):
    company, _ = conversation(client)
    task = create(client, company, "tarefas", TASK)
    as_other_owner(client)
    url = f"/tarefas/{task['id']}"
    assert client.put(url, json=TASK, headers=csrf(client)).status_code == 404
    assert client.delete(url, headers=csrf(client)).status_code == 404


def test_obligation_edit_and_delete(client):
    company, _ = conversation(client)
    item = create(client, company, "obrigacoes", OBLIGATION)
    url = f"/obrigacoes/{item['id']}"
    response = client.put(url, json={"name": "DAS novembro"}, headers=csrf(client))
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["period"]) == ("DAS novembro", None)
    assert client.delete(url, headers=csrf(client)).status_code == 204
    assert client.get(f"/empresas/{company['id']}/obrigacoes").json()["items"] == []


def test_obligation_with_evidence_is_protected(client):
    company, _ = conversation(client)
    item = create(client, company, "obrigacoes", OBLIGATION)
    link_evidence(client, company, item, period="2026-10")
    url = f"/obrigacoes/{item['id']}"
    assert client.delete(url, headers=csrf(client)).status_code == 409
    changed = {**OBLIGATION, "period": "2026-11"}
    assert client.put(url, json=changed, headers=csrf(client)).status_code == 409
    renamed = {**OBLIGATION, "name": "DAS"}
    assert client.put(url, json=renamed, headers=csrf(client)).status_code == 200


def test_obligation_of_other_owner_cannot_be_changed(client):
    company, _ = conversation(client)
    item = create(client, company, "obrigacoes", OBLIGATION)
    as_other_owner(client)
    url = f"/obrigacoes/{item['id']}"
    assert client.put(url, json=OBLIGATION, headers=csrf(client)).status_code == 404
    assert client.delete(url, headers=csrf(client)).status_code == 404


def test_conversation_rename_and_archive(client):
    company, chat = conversation(client)
    url = f"/conversas/{chat['id']}"
    listing = f"/empresas/{company['id']}/conversas"
    renamed = client.patch(url, json={"title": "  DAS de outubro "}, headers=csrf(client))
    assert renamed.status_code == 200
    assert (renamed.json()["title"], renamed.json()["archived_at"]) == ("DAS de outubro", None)
    assert client.patch(url, json={"archived": True}, headers=csrf(client)).json()["archived_at"]
    assert client.get(listing).json()["items"] == []
    (kept,) = client.get(listing, params={"include_archived": True}).json()["items"]
    assert kept["title"] == "DAS de outubro" and kept["archived_at"]
    client.patch(url, json={"archived": False}, headers=csrf(client))
    assert len(client.get(listing).json()["items"]) == 1


def test_conversation_patch_validates_input_and_owner(client):
    _, chat = conversation(client)
    url = f"/conversas/{chat['id']}"
    for data in ({}, {"title": " "}, {"title": None}, {"archived": None}, {"company_id": "x"}):
        assert client.patch(url, json=data, headers=csrf(client)).status_code == 422, data
    as_other_owner(client)
    assert client.patch(url, json={"title": "Minha"}, headers=csrf(client)).status_code == 404


def test_task_from_assistant_can_be_recreated_after_delete(client):
    from app.assistant.models import Message

    company, chat = conversation(client)
    with client.app.state.db_factory() as db:
        message = Message(
            conversation_id=UUID(chat["id"]),
            role="assistant",
            text="Teste",
            context={},
            next_steps=["Conferir documento"],
            citations=[],
            status="answered",
        )
        db.add(message)
        db.commit()
        source = {"source_message_id": str(message.id), "source_step_index": 0}
    first = create(client, company, "tarefas", source)
    client.delete(f"/tarefas/{first['id']}", headers=csrf(client))
    assert create(client, company, "tarefas", source)["id"] != first["id"]


def obligation_state(client, company):
    (item,) = client.get(f"/empresas/{company['id']}/obrigacoes").json()["items"]
    return item["completed"]


def test_obligation_is_completed_by_linked_payment(client):
    company, _ = conversation(client)
    item = create(client, company, "obrigacoes", OBLIGATION)
    assert item["completed"] is False
    link_evidence(client, company, item)
    assert obligation_state(client, company) is True


def test_guide_does_not_complete_obligation(client):
    company, _ = conversation(client)
    item = create(client, company, "obrigacoes", OBLIGATION)
    link_evidence(client, company, item, kind="guide")
    assert obligation_state(client, company) is False
