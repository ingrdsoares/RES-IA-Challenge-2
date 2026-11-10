import hmac
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.access.models import Account, AuthSession
from app.db import get_db
from app.security import digest, require_csrf


def require_account(request: Request, db: Session = Depends(get_db)) -> Account:
    session = db.get(AuthSession, digest(request.cookies.get("sd_session", "")))
    if session is None or session.expires_at <= datetime.now(UTC):
        raise HTTPException(401, "Sessão inválida ou expirada")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        require_csrf(request)
        if not hmac.compare_digest(session.csrf_hash, digest(request.headers["x-csrf-token"])):
            raise HTTPException(403, "Token CSRF inválido")
    account = db.get(Account, session.account_id)
    if account is None:
        raise HTTPException(401, "Sessão inválida")
    return account
