from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access.models import Account, AuthSession
from app.security import digest, token

hasher = PasswordHasher()
_dummy_hash = hasher.hash(token())


@dataclass
class SessionGrant:
    account: Account
    token: str
    csrf: str


def register(email: str, password: str, db: Session) -> Account:
    account = Account(email=email, password_hash=hasher.hash(password))
    db.add(account)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Não foi possível cadastrar este e-mail") from None
    return account


def issue_session(account: Account, db: Session, hours: int = 24) -> SessionGrant:
    session_token, csrf = token(), token()
    db.add(
        AuthSession(
            token_hash=digest(session_token),
            account_id=account.id,
            csrf_hash=digest(csrf),
            expires_at=datetime.now(UTC) + timedelta(hours=hours),
        )
    )
    db.commit()
    return SessionGrant(account, session_token, csrf)


def login(email: str, password: str, db: Session) -> SessionGrant:
    account = db.scalar(select(Account).where(Account.email == email))
    try:
        hasher.verify(account.password_hash if account else _dummy_hash, password)
    except VerificationError:
        raise HTTPException(401, "Credenciais inválidas") from None
    if account is None:
        raise HTTPException(401, "Credenciais inválidas")
    if hasher.check_needs_rehash(account.password_hash):
        account.password_hash = hasher.hash(password)
    return issue_session(account, db)
