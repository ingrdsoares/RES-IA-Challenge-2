from uuid import UUID

from redis import Redis
from rq import Queue, Worker
from sqlalchemy import select

from app.config import Settings
from app.db import session_factory
from app.jobs.models import Operation

# Only trusted application code registers handlers, never request payloads.
HANDLERS = {}


def execute(factory, operation_id: UUID, handlers: dict):
    with factory.begin() as db:
        operation = db.scalar(
            select(Operation).where(Operation.id == operation_id).with_for_update()
        )
        if operation is None or operation.status in ("succeeded", "failed"):
            return
        operation.attempts += 1
        operation.status = "running"
        try:
            with db.begin_nested():
                handler = handlers[operation.kind]
                operation.result = handler(db, operation)
                db.flush()
            operation.status = "succeeded"
            operation.error = None
        except Exception:
            # No exception contents: they may contain private data.
            operation.error = "operation_failed"
            operation.status = "failed" if operation.attempts >= 3 else "queued"
            operation.dispatched_at = None


def run_operation(operation_id: str) -> None:
    settings = Settings()
    factory = session_factory(settings.database_url)
    try:
        execute(factory, UUID(operation_id), HANDLERS)
    finally:
        factory.kw["bind"].dispose()


def main():
    redis = Redis.from_url(Settings().redis_url, socket_timeout=3)
    Worker([Queue("sd", connection=redis)], connection=redis).work()


if __name__ == "__main__":
    main()
