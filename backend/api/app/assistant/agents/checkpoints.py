import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.assistant.agents.models import AgentRun, AgentStep
from app.companies.models import Company
from app.config import Settings
from app.jobs.errors import JobDeferred


class StaleLease(ValueError):
    pass


class BudgetExceeded(ValueError):
    pass


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def claim_step(factory, run_id, step_name, revision, input_data, settings=None):
    settings = settings or Settings()
    now = datetime.now(UTC)
    with factory.begin() as db:
        company_id = db.scalar(select(AgentRun.company_id).where(AgentRun.id == run_id))
        db.scalar(select(Company).where(Company.id == company_id).with_for_update())
        run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if (
            run is None
            or run.revision != revision
            or run.status in ("succeeded", "failed", "awaiting_data")
        ):
            raise StaleLease("Execução indisponível")
        active = db.scalar(
            select(AgentRun.id)
            .where(
                AgentRun.company_id == company_id,
                AgentRun.id != run.id,
                AgentRun.status == "running",
                AgentRun.deadline > now,
            )
            .limit(1)
        )
        if active:
            raise JobDeferred()
        step = db.scalar(
            select(AgentStep).where(
                AgentStep.run_id == run.id,
                AgentStep.revision == revision,
                AgentStep.name == step_name,
            )
        )
        hashed = fingerprint(input_data)
        if step and step.input_hash != hashed:
            raise ValueError("Entrada da etapa diverge")
        if step and step.status == "succeeded":
            return step
        if step and step.status == "running" and step.lease_until > now:
            raise JobDeferred()
        if run.deadline is None:
            run.deadline = now + timedelta(seconds=settings.agent_round_seconds)
        if (
            run.deadline <= now
            or run.calls >= settings.agent_max_calls
            or run.reserved_tokens + settings.num_ctx > settings.agent_token_budget
        ):
            raise BudgetExceeded("Orçamento da execução excedido")
        if step is None:
            step = AgentStep(
                run_id=run.id, revision=revision, name=step_name, input_hash=hashed, attempts=0
            )
            db.add(step)
        if step.attempts >= settings.agent_step_attempts:
            raise BudgetExceeded("Tentativas da etapa excedidas")
        step.attempts += 1
        step.status = "running"
        step.token = uuid4()
        step.lease_until = min(run.deadline, now + timedelta(seconds=settings.agent_timeout + 15))
        run.status = "running"
        run.calls += 1
        run.reserved_tokens += settings.num_ctx
        db.flush()
        return step


def _locked(db, step_id, token):
    run_id = db.scalar(select(AgentStep.run_id).where(AgentStep.id == step_id))
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
    step = db.scalar(select(AgentStep).where(AgentStep.id == step_id).with_for_update())
    if (
        not step
        or step.token != token
        or step.status != "running"
        or step.lease_until <= datetime.now(UTC)
        or step.revision != run.revision
        or run.status != "running"
    ):
        raise StaleLease("Resultado de execução obsoleta")
    return run, step


def finish_step(factory, step_id, token, result, usage):
    with factory.begin() as db:
        _, step = _locked(db, step_id, token)
        step.result = result
        step.usage = usage
        step.model = usage.get("model")
        step.prompt_version = usage.get("prompt_version")
        step.status = "succeeded"
        step.error = None
        step.lease_until = None


def fail_step(factory, step_id, token, error_code, transient):
    with factory.begin() as db:
        run, step = _locked(db, step_id, token)
        step.error = error_code
        step.status = "queued" if transient else "failed"
        step.lease_until = None
        if not transient:
            run.status = "failed"


def save_tool_result(factory, step_id, token, payload):
    with factory.begin() as db:
        _, step = _locked(db, step_id, token)
        if step.tool_result is None:
            step.tool_result = payload
        return step.tool_result
