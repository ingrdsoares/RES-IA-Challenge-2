from test_access import csrf, register

DATA = {
    "cnpj": "11222333000181",
    "cnae": "6201501",
    "size": "ME",
    "regime": "simples",
    "municipality": "Brasília",
    "state": "DF",
}


def test_account_has_multiple_profiles(client):
    assert register(client).status_code == 201
    one = client.post("/empresas", json=DATA, headers=csrf(client))
    assert one.status_code == 201
    two = client.post("/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client))
    assert two.status_code == 201
    rows = client.get("/empresas").json()["items"]
    assert len(rows) == 2
    assert rows[0]["id"] != rows[1]["id"]


def test_other_owner_gets_404(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    assert client.get("/empresas/" + company["id"]).status_code == 404
    assert (
        client.patch(
            "/empresas/" + company["id"], json={"size": "EPP"}, headers=csrf(client)
        ).status_code
        == 404
    )


def test_cnpj_is_immutable(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    assert (
        client.patch(
            "/empresas/" + company["id"], json={"cnpj": "11444777000161"}, headers=csrf(client)
        ).status_code
        == 422
    )


def test_patch_preserves_origin(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    response = client.patch(
        "/empresas/" + company["id"], json={"size": "EPP"}, headers=csrf(client)
    )
    assert response.status_code == 200
    assert response.json()["size"] == "EPP"
    assert response.json()["provenance"]["size"]["origin"] == "declared"


def test_duplicate_cnpj_in_same_account(client):
    register(client)
    assert client.post("/empresas", json=DATA, headers=csrf(client)).status_code == 201
    assert client.post("/empresas", json=DATA, headers=csrf(client)).status_code == 409


def test_invalid_cnpj_rejected(client):
    register(client)
    assert (
        client.post(
            "/empresas", json={**DATA, "cnpj": "11111111111111"}, headers=csrf(client)
        ).status_code
        == 422
    )


def test_company_pagination(client):
    register(client)
    client.post("/empresas", json=DATA, headers=csrf(client))
    client.post("/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client))
    first = client.get("/empresas?limit=1").json()
    assert first["next_cursor"]
    second = client.get("/empresas", params={"limit": 1, "cursor": first["next_cursor"]}).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert second["next_cursor"] is None
