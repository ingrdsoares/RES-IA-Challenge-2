from uuid import UUID, uuid4

from app.assistant.models import Message
from app.telemetria.models import AvaliacaoRag
from sqlalchemy import select
from test_access import csrf, register
from test_conversations import conversation


def question(client):
    _, chat = conversation(client)
    response = client.post(
        f"/conversas/{chat['id']}/mensagens",
        json={"text": "Como funciona o MEI?"},
        headers={**csrf(client), "Idempotency-Key": "feedback"},
    )
    assert response.status_code == 202
    return chat["id"], response.json()["operation_id"]


def answer(client):
    chat_id, operation_id = question(client)
    with client.app.state.db_factory() as db:
        db.add(
            Message(
                conversation_id=UUID(chat_id),
                operation_id=UUID(operation_id),
                role="assistant",
                text="Orientação",
                context={},
                status="answered",
            )
        )
        db.commit()
    return operation_id


def send(client, request_id, **extra):
    return client.post(
        "/rag/feedback",
        json={"request_id": request_id, "useful": True, **extra},
        headers=csrf(client),
    )


def saved(client):
    with client.app.state.db_factory() as db:
        return [
            (row.request_id, row.useful, row.reason) for row in db.scalars(select(AvaliacaoRag))
        ]


def test_assistant_answer_feedback_is_saved(client):
    operation_id = answer(client)
    response = send(client, operation_id, useful=False, reason="incompleta")
    assert response.status_code == 204
    assert saved(client) == [(operation_id, False, "incompleta")]


def test_assistant_feedback_is_updated_not_duplicated(client):
    operation_id = answer(client)
    send(client, operation_id, useful=False, reason="confusa")
    assert send(client, operation_id.upper()).status_code == 204
    assert saved(client) == [(operation_id, True, None)]


def test_feedback_of_other_owner_answer_gets_404(client):
    operation_id = answer(client)
    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    assert send(client, operation_id).status_code == 404
    assert saved(client) == []


def test_feedback_without_answer_gets_404(client):
    _, operation_id = question(client)
    assert send(client, operation_id).status_code == 404
    assert send(client, str(uuid4())).status_code == 404
    assert saved(client) == []
