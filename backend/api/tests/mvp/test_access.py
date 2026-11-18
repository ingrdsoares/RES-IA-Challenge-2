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


@pytest.fixture
def reset_mail(client, monkeypatch):
    from app.access import mail

    settings = client.app.state.settings
    settings.smtp_host = "mail.invalid"
    settings.smtp_from = "acesso@example.test"
    mailbox = []
    monkeypatch.setattr(
        mail, "send_reset_link", lambda _, email, token: mailbox.append((email, token))
    )
    return mailbox


def request_link(client, email):
    return client.post("/auth/password-reset/request", json={"email": email}, headers=csrf(client))


def use_link(client, secret, password="my new longer password"):
    return client.post(
        "/auth/password-reset/confirm",
        json={"token": secret, "password": password},
        headers=csrf(client),
    )


def test_password_recovery_lifecycle(client, reset_mail):
    from app.access.models import Account
    from app.security import digest
    from sqlalchemy import select

    email = "person@example.com"
    assert register(client, email).status_code == 201
    first_session = client.cookies["sd_session"]
    assert client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}, headers=csrf(client)
    ).is_success
    second_session = client.cookies["sd_session"]

    known = request_link(client, " PERSON@Example.com ")
    unknown = request_link(client, "missing@example.com")
    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content == b""
    assert len(reset_mail) == 1
    recipient, old_secret = reset_mail[0]
    assert recipient == email
    assert request_link(client, email).is_success
    secret = reset_mail[-1][1]
    with client.app.state.db_factory() as db:
        account = db.scalar(select(Account).where(Account.email == email))
        assert account.reset_token_hash == digest(secret)
        assert (
            datetime.now(UTC)
            < account.reset_expires_at
            <= datetime.now(UTC) + timedelta(minutes=30)
        )

    assert use_link(client, old_secret).status_code == 400
    assert use_link(client, secret, "short").status_code == 422
    assert use_link(client, secret).status_code == 204
    assert use_link(client, secret).status_code == 400
    for session in (first_session, second_session):
        client.cookies.clear()
        client.cookies.set("sd_session", session)
        assert client.get("/auth/session").status_code == 401
    client.cookies.clear()
    for password, status in [(PASSWORD, 401), ("my new longer password", 200)]:
        assert (
            client.post(
                "/auth/login", json={"email": email, "password": password}, headers=csrf(client)
            ).status_code
            == status
        )


def test_reset_expiry_csrf_and_throttle(client, reset_mail):
    from app.access.models import Account
    from sqlalchemy import update

    assert register(client).is_success
    payload = {"email": "person@example.com"}
    assert client.post("/auth/password-reset/request", json=payload).status_code == 403
    assert request_link(client, payload["email"]).is_success
    secret = reset_mail[0][1]
    assert (
        client.post(
            "/auth/password-reset/confirm", json={"token": secret, "password": PASSWORD}
        ).status_code
        == 403
    )
    with client.app.state.db_factory() as db:
        db.execute(
            update(Account).values(reset_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        db.commit()
    assert use_link(client, secret).status_code == 400
    for _ in range(4):
        assert request_link(client, payload["email"]).status_code == 204
    assert request_link(client, payload["email"]).status_code == 429
    assert len(reset_mail) == 5
