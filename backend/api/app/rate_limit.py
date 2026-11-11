import logging
import time

from fastapi import HTTPException, Request, Response
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# Script Lua atomico para incremento com janela de tempo fixa
LUA_RATE_LIMIT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window)
end
local ttl = redis.call('TTL', key)
if ttl == -1 then
    redis.call('EXPIRE', key, window)
    ttl = window
end

return {current, ttl}
"""


def get_client_identifier(request: Request) -> str:
    """Extrai identificador único do cliente para o rate limit (Sessão ou IP)."""
    session = request.cookies.get("sd_session")
    if session:
        return f"acc_{session[:16]}"

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    return f"ip_{client_ip}"


class RateLimiter:
    """Dependency do FastAPI para aplicacao de Rate Limit via Redis."""

    def __init__(
        self,
        requests_limit: int | None = None,
        window_seconds: int = 60,
        namespace: str = "general",
    ):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.namespace = namespace

    def __call__(self, request: Request, response: Response = None):
        settings = getattr(request.app.state, "settings", None)
        if settings and not getattr(settings, "rate_limit_enabled", True):
            return

        # Determina o limite da rota (especifico ou padrao das configuracoes)
        limit = self.requests_limit
        if limit is None and settings:
            if self.namespace == "ai_rag":
                limit = getattr(settings, "rate_limit_ai_per_minute", 20)
            elif self.namespace == "auth":
                limit = getattr(settings, "rate_limit_auth_per_minute", 10)
            else:
                limit = getattr(settings, "rate_limit_requests_per_minute", 120)

        limit = limit or 120
        redis_client = getattr(request.app.state, "redis", None)
        if not redis_client:
            return

        identifier = get_client_identifier(request)
        key = f"rl:{self.namespace}:{identifier}"

        try:
            result = redis_client.eval(LUA_RATE_LIMIT, 1, key, limit, self.window_seconds)
            current, ttl = result[0], result[1]
            remaining = max(0, limit - current)
            reset_time = int(time.time()) + max(0, ttl)

            if response is not None:
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset_time)

            if current > limit:
                logger.warning(
                    "Rate limit excedido para %s no namespace %s (tentativa %s de %s)",
                    identifier,
                    self.namespace,
                    current,
                    limit,
                )
                headers = {
                    "Retry-After": str(max(1, ttl)),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                }
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "rate_limit_exceeded",
                        "message": f"Limite de requisições excedido. Tente novamente em {ttl} segundos.",
                    },
                    headers=headers,
                )
        except RedisError as e:
            # Em caso de falha transitória do Redis, registra aviso e permite a requisição (fail-open resiliente)
            logger.warning("Falha de comunicação com Redis durante rate limiting: %s", e)
            return
