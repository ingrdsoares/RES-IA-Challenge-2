from test_access import csrf, register
from test_companies import DATA


def conversation(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    response = client.post(
        "/empresas/" + company["id"] + "/conversas", json={"title": "Teste"}, headers=csrf(client)
    )
    assert response.status_code == 201
    return company, response.json()


def test_retry_does_not_duplicate_message(client):
    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    headers = {**csrf(client), "Idempotency-Key": "message-1"}
    first = client.post(url, json={"text": "Como funciona o MEI?"}, headers=headers)
    assert first.status_code == 202
    second = client.post(url, json={"text": "Como funciona o MEI?"}, headers=headers)
    assert first.json()["operation_id"] == second.json()["operation_id"]
    assert len(client.get(url).json()["items"]) == 1
    assert client.post(url, json={"text": "Outra pergunta"}, headers=headers).status_code == 409


def test_ambiguous_period_requires_confirmation(client):
    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    response = client.post(
        url,
        json={"text": "Paguei o DAS de outubro?"},
        headers={**csrf(client), "Idempotency-Key": "ambiguous"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "awaiting_data"
    assert "period" in response.json()["missing_fields"]
    operation_id = response.json()["operation_id"]
    confirmed = client.post(
        url,
        json={
            "text": "Confirmo outubro de 2026",
            "confirmation_for": operation_id,
            "confirmation": {"period": "2026-10"},
        },
        headers={**csrf(client), "Idempotency-Key": "confirm"},
    )
    assert confirmed.status_code == 202
    assert confirmed.json()["operation_id"] == operation_id
    assert confirmed.json()["status"] == "queued"


def test_company_is_fixed_for_conversation(client):
    company, chat = conversation(client)
    client.post("/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client))
    url = "/conversas/" + chat["id"]
    assert client.get(url).json()["company_id"] == company["id"]
    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    assert client.get(url).status_code == 404
    assert client.get(url + "/mensagens").status_code == 404


def test_profile_change_does_not_rewrite_snapshot(client):
    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    client.post(
        url, json={"text": "O que é MEI?"}, headers={**csrf(client), "Idempotency-Key": "snap"}
    )
    client.patch("/empresas/" + company["id"], json={"regime": "outro"}, headers=csrf(client))
    assert client.get(url).json()["items"][0]["context"]["company"]["regime"] == "simples"


def test_confirmation_is_idempotent_and_scoped(client):
    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    first = client.post(
        url, json={"text": "Paguei o DAS?"}, headers={**csrf(client), "Idempotency-Key": "one"}
    ).json()
    data = {
        "text": "Confirmo",
        "confirmation_for": first["operation_id"],
        "confirmation": {"period": "2026-10"},
    }
    headers = {**csrf(client), "Idempotency-Key": "confirm"}
    assert client.post(url, json=data, headers=headers).status_code == 202
    assert (
        client.post(url, json=data, headers=headers).json()["operation_id"] == first["operation_id"]
    )
    assert len(client.get(url).json()["items"]) == 2
    other = client.post(
        "/empresas/" + company["id"] + "/conversas", json={}, headers=csrf(client)
    ).json()
    assert (
        client.post(
            "/conversas/" + other["id"] + "/mensagens",
            json=data,
            headers={**csrf(client), "Idempotency-Key": "other"},
        ).status_code
        == 404
    )


def test_history_pagination_keeps_messages_reachable(client):
    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    for number in range(2):
        client.post(
            url,
            json={"text": f"Pergunta {number}"},
            headers={**csrf(client), "Idempotency-Key": str(number)},
        )
    first = client.get(url, params={"limit": 1}).json()
    assert first["next_cursor"]
    second = client.get(url, params={"limit": 1, "cursor": first["next_cursor"]}).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert second["next_cursor"] is None
