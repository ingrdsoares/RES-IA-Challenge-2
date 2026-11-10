from test_access import csrf
from test_conversations import conversation


def test_task_completion_does_not_change_fiscal_verification(client):
    company, _ = conversation(client)
    base = "/empresas/" + company["id"]
    response = client.post(
        base + "/tarefas",
        json={"title": "Conferir guia", "period": "2026-10"},
        headers=csrf(client),
    )
    assert response.status_code == 201
    task_id = response.json()["id"]
    url = "/tarefas/" + task_id
    headers = {**csrf(client), "Idempotency-Key": "done"}
    assert client.patch(url, json={"completed": True}, headers=headers).status_code == 200
    assert client.patch(url, json={"completed": True}, headers=headers).status_code == 200
    assert len(client.get(url + "/historico").json()["items"]) == 1
    assert (
        client.get(base + "/situacao-fiscal").json()["obligations"]["verification"] == "unverified"
    )
    assert client.patch(url, json={"completed": False}, headers=headers).status_code == 409
    assert (
        client.patch(
            url, json={"completed": False}, headers={**csrf(client), "Idempotency-Key": "undo"}
        ).status_code
        == 200
    )
    assert len(client.get(url + "/historico").json()["items"]) == 2


def test_tasks_paginate_and_steps_require_explicit_action(client):
    from uuid import UUID

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
        message_id = str(message.id)
    base = "/empresas/" + company["id"] + "/tarefas"
    assert client.get(base).json()["items"] == []
    data = {"source_message_id": message_id, "source_step_index": 0}
    first = client.post(base, json=data, headers=csrf(client)).json()
    assert client.post(base, json=data, headers=csrf(client)).json()["id"] == first["id"]
    client.post(base, json={"title": "Outra"}, headers=csrf(client))
    page = client.get(base, params={"limit": 1}).json()
    assert page["next_cursor"]
    after = client.get(base, params={"limit": 1, "cursor": page["next_cursor"]}).json()
    assert after["items"][0]["id"] != page["items"][0]["id"]
