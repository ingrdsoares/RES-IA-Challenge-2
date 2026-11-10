from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.access import service
from app.access.models import Account, AuthSession
from app.access.schemas import AccountView, Credentials
from app.db import get_db
from app.dependencies import require_account
from app.security import digest, require_csrf, token

router = APIRouter(prefix="/auth", tags=["Acesso"])


def set_cookie(response: Response, request: Request, key: str, value: str, max_age: int = 86400):
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/csrf")
def csrf(request: Request, response: Response, db: Session = Depends(get_db)):
    session_token = request.cookies.get("sd_session")
    value = token()
    if session_token:
        session = db.get(AuthSession, digest(session_token))
        if session:
            # Keep the session-bound token stable across tabs.
            existing = request.cookies.get("sd_csrf", "")
            if digest(existing) == session.csrf_hash:
                value = existing
            else:
                session.csrf_hash = digest(value)
                db.commit()
    set_cookie(response, request, "sd_csrf", value)
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": value}


def throttle(request: Request, email: str):
    redis = request.app.state.redis
    keys = [
        "login:ip:" + digest(request.client.host if request.client else "unknown"),
        "login:email:" + digest(email),
    ]
    script = """local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"""
    try:
        counts = [redis.eval(script, 1, key, 900) for key in keys]
    except RedisError:
        raise HTTPException(503, "Acesso temporariamente indisponível") from None
    if max(counts) > 5:
        raise HTTPException(429, "Limite de tentativas excedido", headers={"Retry-After": "900"})


def grant_response(grant: service.SessionGrant, request: Request, response: Response):
    set_cookie(response, request, "sd_session", grant.token)
    set_cookie(response, request, "sd_csrf", grant.csrf)
    response.headers["Cache-Control"] = "no-store"
    return grant.account


@router.post(
    "/register", response_model=AccountView, status_code=201, dependencies=[Depends(require_csrf)]
)
def register(
    data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)
):
    throttle(request, data.email)
    account = service.register(data.email, data.password, db)
    return grant_response(service.issue_session(account, db), request, response)


@router.post("/login", response_model=AccountView, dependencies=[Depends(require_csrf)])
def login(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, data.email)
    return grant_response(service.login(data.email, data.password, db), request, response)


@router.get("/session", response_model=AccountView)
def current(response: Response, account: Account = Depends(require_account)):
    response.headers["Cache-Control"] = "no-store"
    return account


@router.post("/logout", status_code=204)
def logout(
    request: Request, db: Session = Depends(get_db), account: Account = Depends(require_account)
):
    session = db.get(AuthSession, digest(request.cookies["sd_session"]))
    db.delete(session)
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie("sd_session", path="/")
    response.delete_cookie("sd_csrf", path="/")
    return response
