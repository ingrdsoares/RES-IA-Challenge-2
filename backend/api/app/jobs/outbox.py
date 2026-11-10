import time
from datetime import UTC, datetime, timedelta

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from sqlalchemy import or_, select

from app.config import Settings
from app.db import session_factory
from app.jobs.models import Operation


def dispatch(factory, redis: Redis) -> int:
    count = 0
    with factory.begin() as db:
        operations = db.scalars(
            select(Operation)
            .where(
                Operation.status == "queued",
                or_(
                    Operation.dispatched_at.is_(None),
                    Operation.dispatched_at < datetime.now(UTC) - timedelta(minutes=15),
                ),
            )
            .with_for_update(skip_locked=True)
            .limit(100)
        ).all()
        for operation in operations:
            try:
                Queue("sd", connection=redis).enqueue(
                    "app.jobs.worker.run_operation",
                    str(operation.id),
                    job_timeout=600,
                    result_ttl=0,
                    failure_ttl=3600,
                )
            except RedisError:
                break
            operation.dispatched_at = datetime.now(UTC)
            count += 1
    return count


def main():
    settings = Settings()
    factory = session_factory(settings.database_url)
    redis = Redis.from_url(settings.redis_url, socket_timeout=3)
    while True:
        dispatch(factory, redis)
        time.sleep(1)


if __name__ == "__main__":
    main()
