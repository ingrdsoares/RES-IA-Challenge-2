from test_access import PASSWORD, csrf, register

DATA = {
    "cnpj": "11222333000181",
    "cnae": "6201501",
    "size": "ME",
    "regime": "simples",
    "municipality": "Brasília",
    "state": "DF",
}


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
    assert register(client).status_code == 201
    one = client.post("/empresas", json=DATA, headers=csrf(client))
    two = client.post("/empresas", json={**DATA, "cnpj": "11444777000161"}, headers=csrf(client))
    assert one.status_code == two.status_code == 201
    rows = client.get("/empresas").json()["items"]
    assert len(rows) == 2
    assert {row["id"] for row in rows} == {one.json()["id"], two.json()["id"]}
    first = client.get("/empresas?limit=1").json()
    assert first["next_cursor"]
    second = client.get("/empresas", params={"limit": 1, "cursor": first["next_cursor"]}).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert second["next_cursor"] is None


def test_oversized_profile_fields_rejected(client):
    register(client)
    for field, length in (("size", 31), ("regime", 41)):
        response = client.post(
            "/empresas", json={**DATA, field: "x" * length}, headers=csrf(client)
        )
        assert response.status_code == 422


def test_revenue_starts_without_value(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    response = client.get(f"/empresas/{company['id']}/faturamento/2026")
    assert response.status_code == 200
    assert response.json() == {"year": 2026, "amount": None, "updated_at": None}


def test_revenue_is_kept_after_new_login(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    url = f"/empresas/{company['id']}/faturamento/2026"
    saved = client.put(url, json={"amount": "48500.10"}, headers=csrf(client))
    assert saved.status_code == 200
    client.post("/auth/logout", headers=csrf(client))
    client.cookies.clear()
    client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": PASSWORD},
        headers=csrf(client),
    )
    body = client.get(url).json()
    assert body["amount"] == "48500.10"
    assert body["updated_at"]


def test_revenue_put_replaces_value_of_same_year_only(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    url = f"/empresas/{company['id']}/faturamento/"
    client.put(url + "2025", json={"amount": "10.00"}, headers=csrf(client))
    client.put(url + "2026", json={"amount": "20.00"}, headers=csrf(client))
    client.put(url + "2026", json={"amount": "30.00"}, headers=csrf(client))
    assert client.get(url + "2025").json()["amount"] == "10.00"
    assert client.get(url + "2026").json()["amount"] == "30.00"


def test_revenue_of_other_owner_gets_404(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    url = f"/empresas/{company['id']}/faturamento/2026"
    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    assert client.get(url).status_code == 404
    assert client.put(url, json={"amount": "1.00"}, headers=csrf(client)).status_code == 404


def test_invalid_revenue_rejected(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    url = f"/empresas/{company['id']}/faturamento/"
    for amount in ("-1.00", "1.001", "abc", 10.5, None):
        response = client.put(url + "2026", json={"amount": amount}, headers=csrf(client))
        assert response.status_code == 422, amount
    for year in ("1999", "2101", "abc"):
        assert client.get(url + year).status_code == 422, year
