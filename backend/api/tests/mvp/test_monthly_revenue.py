import pytest
from test_access import csrf, register
from test_companies import DATA

ZERO = {
    "trade_without_invoice": "0.00",
    "trade_with_invoice": "0.00",
    "industry_without_invoice": "0.00",
    "industry_with_invoice": "0.00",
    "services_without_invoice": "0.00",
    "services_with_invoice": "0.00",
}


@pytest.fixture
def base(client):
    register(client)
    company = client.post("/empresas", json=DATA, headers=csrf(client)).json()
    return f"/empresas/{company['id']}"


def put(client, base, period, **amounts):
    return client.put(
        f"{base}/faturamento-mensal/{period}", json={**ZERO, **amounts}, headers=csrf(client)
    )


def months(client, base, start="2026-01", end="2026-12"):
    response = client.get(f"{base}/faturamento-mensal", params={"from": start, "to": end})
    assert response.status_code == 200
    return response.json()["items"]


def test_month_is_saved_with_total(client, base):
    response = put(
        client, base, "2026-10", trade_with_invoice="1000.10", services_without_invoice="50.05"
    )
    assert response.status_code == 200
    (item,) = months(client, base)
    assert item["period"] == "2026-10"
    assert item["trade_with_invoice"] == "1000.10"
    assert item["total"] == "1050.15"
    assert item["updated_at"]


def test_month_is_replaced_and_listed_in_order(client, base):
    put(client, base, "2026-11", services_with_invoice="10.00")
    put(client, base, "2026-02", services_with_invoice="5.00")
    put(client, base, "2026-11", services_with_invoice="20.00")
    assert [(m["period"], m["total"]) for m in months(client, base)] == [
        ("2026-02", "5.00"),
        ("2026-11", "20.00"),
    ]
    assert [m["period"] for m in months(client, base, "2026-03", "2027-02")] == ["2026-11"]


def test_month_can_be_removed(client, base):
    put(client, base, "2026-10", services_with_invoice="10.00")
    url = f"{base}/faturamento-mensal/2026-10"
    assert client.delete(url, headers=csrf(client)).status_code == 204
    assert months(client, base) == []
    assert client.delete(url, headers=csrf(client)).status_code == 404


def test_annual_revenue_uses_months_once_launched(client, base):
    annual = f"{base}/faturamento/2026"
    client.put(annual, json={"amount": "48500.00"}, headers=csrf(client))
    assert client.get(annual).json()["source"] == "annual"
    put(client, base, "2026-01", services_with_invoice="1000.00")
    put(client, base, "2026-02", trade_with_invoice="500.50")
    put(client, base, "2025-12", trade_with_invoice="9999.00")
    body = client.get(annual).json()
    assert (body["amount"], body["source"]) == ("1500.50", "monthly")
    blocked = client.put(annual, json={"amount": "1.00"}, headers=csrf(client))
    assert blocked.status_code == 409


def test_annual_value_returns_when_months_are_removed(client, base):
    annual = f"{base}/faturamento/2026"
    client.put(annual, json={"amount": "48500.00"}, headers=csrf(client))
    put(client, base, "2026-01", services_with_invoice="1000.00")
    client.delete(f"{base}/faturamento-mensal/2026-01", headers=csrf(client))
    body = client.get(annual).json()
    assert (body["amount"], body["source"]) == ("48500.00", "annual")


def test_month_without_revenue_counts_as_launched(client, base):
    put(client, base, "2026-01")
    body = client.get(f"{base}/faturamento/2026").json()
    assert (body["amount"], body["source"]) == ("0.00", "monthly")


def test_invalid_month_is_rejected(client, base):
    for period in ("2026-13", "2026", "1999-01", "2101-01", "abc"):
        assert put(client, base, period).status_code == 422, period
    for amount in ("-1.00", "1.001", "abc", 10.5, None):
        assert put(client, base, "2026-10", services_with_invoice=amount).status_code == 422
    missing = {k: v for k, v in ZERO.items() if k != "trade_with_invoice"}
    url = f"{base}/faturamento-mensal/2026-10"
    assert client.put(url, json=missing, headers=csrf(client)).status_code == 422
    params = {"from": "2026-12", "to": "2026-01"}
    assert client.get(f"{base}/faturamento-mensal", params=params).status_code == 422
    params = {"from": "2020-01", "to": "2026-01"}
    assert client.get(f"{base}/faturamento-mensal", params=params).status_code == 422


def test_months_of_other_owner_get_404(client, base):
    put(client, base, "2026-10", services_with_invoice="10.00")
    client.post("/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    url = f"{base}/faturamento-mensal"
    assert client.get(url, params={"from": "2026-01", "to": "2026-12"}).status_code == 404
    assert put(client, base, "2026-10").status_code == 404
    assert client.delete(f"{url}/2026-10", headers=csrf(client)).status_code == 404
