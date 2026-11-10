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
    script = """
    for _,key in ipairs(KEYS) do
      if tonumber(redis.call('GET',key) or '0') >= 5 then return 0 end
    end
    for _,key in ipairs(KEYS) do
      local n=redis.call('INCR',key)
      if n==1 then redis.call('EXPIRE',key,ARGV[1]) end
    end
    return 1
    """
    try:
        allowed = redis.eval(script, len(keys), *keys, 900)
    except RedisError:
        raise HTTPException(503, "Acesso temporariamente indisponível") from None
    if not allowed:
        raise HTTPException(429, "Limite de tentativas excedido", headers={"Retry-After": "900"})
    return keys


def release_success(request, keys):
    script = "if redis.call('EXISTS',KEYS[1])==1 then local n=redis.call('DECR',KEYS[1]); if n<=0 then redis.call('DEL',KEYS[1]) end end; return 1"
    try:
        for key in keys:
            request.app.state.redis.eval(script, 1, key)
    except RedisError:
        # A reserved attempt can expire normally; never invalidate a committed session.
        pass


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
    keys = throttle(request, data.email)
    account = service.register(data.email, data.password, db)
    grant = service.issue_session(account, db)
    release_success(request, keys)
    return grant_response(grant, request, response)


@router.post("/login", response_model=AccountView, dependencies=[Depends(require_csrf)])
def login(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    keys = throttle(request, data.email)
    grant = service.login(data.email, data.password, db)
    release_success(request, keys)
    return grant_response(grant, request, response)


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
