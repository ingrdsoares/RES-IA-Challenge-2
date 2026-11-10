from datetime import UTC, datetime, timedelta

import pytest

PASSWORD = "long enough password"
ORIGIN = "http://testserver"


def csrf(client):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def register(client, email="person@example.com"):
    return client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}, headers=csrf(client)
    )


def test_register_login_logout(client):
    response = register(client)
    assert response.status_code == 201
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/auth/session").json()["email"] == "person@example.com"
    assert client.post("/auth/logout", headers=csrf(client)).status_code == 204
    assert client.get("/auth/session").status_code == 401
    login = client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": PASSWORD},
        headers=csrf(client),
    )
    assert login.status_code == 200


def test_csrf_required_on_login(client):
    assert (
        client.post(
            "/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        ).status_code
        == 403
    )


def test_duplicate_normalized_email(client):
    assert register(client, " Person@Example.com ").status_code == 201
    assert register(client, "person@example.com").status_code == 409


def test_cross_origin_rejected(client):
    headers = csrf(client)
    headers["Origin"] = "https://attacker.invalid"
    assert (
        client.post(
            "/auth/register",
            json={"email": "person@example.com", "password": PASSWORD},
            headers=headers,
        ).status_code
        == 403
    )


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_length_rejected(client, password):
    assert (
        client.post(
            "/auth/register",
            json={"email": "person@example.com", "password": password},
            headers=csrf(client),
        ).status_code
        == 422
    )


def test_login_rate_limit(client):
    headers = csrf(client)
    for _ in range(5):
        assert (
            client.post(
                "/auth/login",
                json={"email": "missing@example.com", "password": PASSWORD},
                headers=headers,
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": PASSWORD},
            headers=headers,
        ).status_code
        == 429
    )


def test_session_expiry(client):
    from app.access.models import AuthSession
    from sqlalchemy import update

    assert register(client).status_code == 201
    with client.app.state.db_factory() as db:
        db.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    assert client.get("/auth/session").status_code == 401


def test_session_token_stored_hashed(client):
    from app.access.models import Account, AuthSession
    from sqlalchemy import select

    assert register(client).status_code == 201
    with client.app.state.db_factory() as db:
        account = db.scalar(select(Account))
        session = db.scalar(select(AuthSession))
        assert account.password_hash.startswith("$argon2id$")
        assert PASSWORD not in account.password_hash
        assert session.token_hash != client.cookies["sd_session"]
        assert len(session.token_hash) == 64


def test_logout_revokes_stolen_cookie(client):
    assert register(client).status_code == 201
    stolen = client.cookies["sd_session"]
    assert client.post("/auth/logout", headers=csrf(client)).status_code == 204
    client.cookies.set("sd_session", stolen)
    assert client.get("/auth/session").status_code == 401


def test_legacy_rag_requires_session(client):
    assert client.post("/rag/query", json={"question": "Pergunta"}).status_code == 401


def test_secure_cookie_in_production(client):
    client.base_url = "https://testserver"
    client.app.state.settings.allowed_origins = [ORIGIN]
    client.app.state.settings.cookie_secure = True
    response = register(client)
    assert response.status_code == 201
    assert "secure" in response.headers["set-cookie"].lower()


def test_validation_never_echoes_password(client):
    response = client.post(
        "/auth/register", json={"email": "bad", "password": "my-secret"}, headers=csrf(client)
    )
    assert response.status_code == 422
    assert "my-secret" not in response.text
    assert response.json()["error"]["code"] == "validation_error"


def test_successful_logins_do_not_consume_failure_budget(client):
    assert register(client).status_code == 201
    for _ in range(6):
        assert (
            client.post(
                "/auth/login",
                json={"email": "person@example.com", "password": PASSWORD},
                headers=csrf(client),
            ).status_code
            == 200
        )
