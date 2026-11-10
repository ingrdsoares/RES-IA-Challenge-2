import pytest
from app.legal import models as legal_models  # noqa: F401
from app.main import create_app
from fastapi.testclient import TestClient

ORIGIN = "http://testserver"


@pytest.fixture
def client(service):
    from app.config import Settings
    from app.db import Base, session_factory
    from redis import Redis

    settings = Settings(
        database_url="postgresql+psycopg://postgres:sd_test_local@localhost:15432/sd_test",
        redis_url="redis://localhost:16379/15",
        cookie_secure=False,
        allowed_origins=[ORIGIN],
    )
    factory = session_factory(settings.database_url)
    Base.metadata.drop_all(factory.kw["bind"])
    Base.metadata.create_all(factory.kw["bind"])
    Redis.from_url(settings.redis_url).flushdb()
    with TestClient(create_app(settings=settings, service=service)) as client:
        yield client
