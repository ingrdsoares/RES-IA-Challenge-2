from uuid import uuid4

import pytest
from fastapi import HTTPException


def test_duplicate_operation_returns_same_id(client):
    from app.jobs.service import enqueue

    with client.app.state.db_factory() as db:
        first = enqueue(db, "test", None, None, "same", {"a": 1})
        second = enqueue(db, "test", None, None, "same", {"a": 1})
        assert first.id == second.id


def test_changed_payload_conflicts(client):
    from app.jobs.service import enqueue

    with client.app.state.db_factory() as db:
        enqueue(db, "test", None, None, "same", {"a": 1})
        with pytest.raises(HTTPException) as error:
            enqueue(db, "test", None, None, "same", {"a": 2})
        assert error.value.status_code == 409


def test_outbox_recovers_after_redis_failure(client):
    from app.jobs.outbox import dispatch
    from app.jobs.service import enqueue
    from redis import Redis

    with client.app.state.db_factory() as db:
        operation = enqueue(db, "test", None, None, "recovery", {})
        db.commit()
        operation_id = operation.id
    broken = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1)
    assert dispatch(client.app.state.db_factory, broken) == 0
    assert dispatch(client.app.state.db_factory, client.app.state.redis) == 1
    from rq import Queue

    job = Queue("sd", connection=client.app.state.redis).get_jobs()[0]
    assert job.args == (str(operation_id),)


def test_retry_exhaustion(client):
    from app.jobs.models import Operation
    from app.jobs.service import enqueue
    from app.jobs.worker import execute

    with client.app.state.db_factory() as db:
        operation = enqueue(db, "test", None, None, "failure", {})
        db.commit()
        operation_id = operation.id

    def fail(db, operation):
        raise RuntimeError("secret credentials")

    for _ in range(5):
        execute(client.app.state.db_factory, operation_id, {"test": fail})
    with client.app.state.db_factory() as db:
        operation = db.get(Operation, operation_id)
        assert operation.attempts == 3
        assert operation.status == "failed"
        assert "secret" not in operation.error


def test_private_operation_requires_owner(client):
    from app.jobs.service import enqueue
    from test_access import register

    register(client)
    with client.app.state.db_factory() as db:
        operation = enqueue(db, "test", None, None, "admin-only", {})
        db.commit()
        operation_id = operation.id
    assert client.get("/operacoes/" + str(operation_id)).status_code == 404
    assert client.get("/operacoes/" + str(uuid4())).status_code == 404
