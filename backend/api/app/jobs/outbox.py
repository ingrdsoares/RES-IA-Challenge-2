import time
from datetime import UTC, datetime, timedelta

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from sqlalchemy import and_, exists, or_, select

from app.assistant.agents.models import AgentRun, AgentStep
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
                    and_(
                        Operation.kind == "assistant.answer",
                        Operation.dispatched_at < datetime.now(UTC) - timedelta(seconds=30),
                        ~exists(
                            select(AgentStep.id)
                            .join(AgentRun, AgentStep.run_id == AgentRun.id)
                            .where(
                                AgentRun.operation_id == Operation.id,
                                AgentStep.status == "running",
                                AgentStep.lease_until > datetime.now(UTC),
                            )
                        ),
                    ),
                    exists(
                        select(AgentStep.id)
                        .join(AgentRun, AgentStep.run_id == AgentRun.id)
                        .where(
                            AgentRun.operation_id == Operation.id,
                            AgentStep.status == "running",
                            AgentStep.lease_until <= datetime.now(UTC),
                        )
                    ),
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
                    job_timeout=660,
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
