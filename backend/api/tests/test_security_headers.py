from unittest.mock import MagicMock

from app.main import create_app
from app.rate_limit import RateLimiter
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient


def test_security_headers_present():
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "content-security-policy" in r.headers
        assert "permissions-policy" in r.headers


def test_rate_limiter_allows_under_limit():
    app = FastAPI()
    limiter = RateLimiter(requests_limit=5, window_seconds=60, namespace="test")

    # Mock do Redis
    mock_redis = MagicMock()
    mock_redis.eval.return_value = [1, 59]  # 1st request, 59s TTL
    app.state.redis = mock_redis
    app.state.settings = MagicMock(rate_limit_enabled=True)

    @app.get("/test-endpoint")
    def endpoint(request: Request, response: Response):
        limiter(request, response)
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/test-endpoint")
    assert r.status_code == 200
    assert r.headers.get("x-ratelimit-limit") == "5"
    assert r.headers.get("x-ratelimit-remaining") == "4"


def test_rate_limiter_blocks_when_exceeded():
    app = FastAPI()
    limiter = RateLimiter(requests_limit=2, window_seconds=60, namespace="test_block")

    mock_redis = MagicMock()
    mock_redis.eval.return_value = [3, 45]  # 3rd request, limit is 2
    app.state.redis = mock_redis
    app.state.settings = MagicMock(rate_limit_enabled=True)

    @app.get("/test-blocked")
    def endpoint(request: Request, response: Response):
        limiter(request, response)
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/test-blocked")
    assert r.status_code == 429
    assert "retry-after" in r.headers
    data = r.json()
    assert "detail" in data
    assert data["detail"]["code"] == "rate_limit_exceeded"
