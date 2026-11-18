"""Sequential orchestration; external calls never share a database transaction."""

import re
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError
from sqlalchemy import select, tuple_

from app.assistant.agents.checkpoints import (
    StaleLease,
    claim_step,
    fail_step,
    finish_step,
    save_tool_result,
)
from app.assistant.agents.contracts import (
    ActionPlan,
    FinalAnswer,
    FiscalResult,
    LegalResult,
    SupervisorPlan,
)
from app.assistant.agents.llm import AgentModel
from app.assistant.agents.models import AgentRun
from app.assistant.agents.tools import AgentTools
from app.assistant.agents.validation import render_answer, validate_results
from app.assistant.models import Conversation, Message
from app.companies.service import require_company
from app.config import Settings
from app.jobs.errors import JobDeferred
from app.jobs.models import Operation


def ensure_run(db, operation, conversation, context):
    run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation.id))
    if run is None:
        run = AgentRun(
            operation_id=operation.id,
            conversation_id=conversation.id,
            company_id=operation.company_id,
            owner_id=operation.owner_id,
            context=context,
            status=operation.status,
        )
        db.add(run)
        db.flush()
    return run


def execute_run(factory, operation_id, model=None, tools=None, settings=None):
    settings = settings or Settings()
    model = model or AgentModel(settings)
    with factory.begin() as db:
        operation = db.scalar(
            select(Operation).where(Operation.id == operation_id).with_for_update()
        )
        if operation is None or operation.status in ("succeeded", "failed", "awaiting_data"):
            return
        user = db.scalar(
            select(Message).where(Message.operation_id == operation_id, Message.role == "user")
        )
        if user is None:
            raise ValueError("Mensagem ausente")
        conversation = db.get(Conversation, user.conversation_id)
        require_company(db, operation.owner_id, operation.company_id)
        if conversation.company_id != operation.company_id:
            raise ValueError("Empresa divergente")
        earlier = db.scalar(
            select(Message.id)
            .join(Operation, Message.operation_id == Operation.id)
            .where(
                Message.conversation_id == conversation.id,
                Message.role == "user",
                Operation.kind == "assistant.answer",
                tuple_(Message.created_at, Message.id) < tuple_(user.created_at, user.id),
                Operation.status.in_(["queued", "running", "awaiting_data"]),
            )
            .limit(1)
        )
        if earlier:
            return
        run = ensure_run(db, operation, conversation, user.context)
        run_id, revision, context, question = run.id, run.revision, run.context, user.text
        history = list(
            db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    tuple_(Message.created_at, Message.id) < tuple_(user.created_at, user.id),
                )
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(4)
            )
        )
        history = [{"role": item.role, "text": item.text[:400]} for item in reversed(history)]
        owner_id, company_id = run.owner_id, run.company_id
        calculation = operation.payload.get("request", {}).get("calculation")
        if context.get("calculation_input"):
            calculation = context["calculation_input"]
    tools = tools or AgentTools(factory, owner_id, company_id, context, settings)

    def stage(name, schema, payload, prepare=None):
        step = claim_step(factory, run_id, name, revision, payload, settings)
        if step.status == "succeeded":
            return schema.model_validate(step.result), step
        try:
            actual = step.tool_result
            if actual is None:
                actual = prepare(step) if prepare else payload
                actual = save_tool_result(factory, step.id, step.token, actual)
                step.tool_result = actual
            result, usage = model.generate(
                name,
                schema,
                actual,
                min(
                    settings.agent_timeout,
                    max(1, (step.lease_until - datetime.now(UTC)).total_seconds() - 15),
                ),
                settings.num_predict,
            )
            finish_step(factory, step.id, step.token, result.model_dump(mode="json"), usage)
            return result, step
        except (httpx.HTTPError, ConnectionError, TimeoutError):
            fail_step(factory, step.id, step.token, "dependency_unavailable", True)
            raise JobDeferred() from None
        except (ValueError, ValidationError):
            fail_step(factory, step.id, step.token, "invalid_agent_result", False)
            raise

    def pause(fields):
        with factory.begin() as db:
            current = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if current.revision != revision:
                raise StaleLease("Contexto alterado")
            current.status = "awaiting_data"
            current.context = {**current.context, "missing_fields": fields}
            op = db.get(Operation, operation_id)
            op.status, op.result = (
                "awaiting_data",
                {"missing_fields": fields, "run_id": str(run_id)},
            )
            message = db.get(Message, user.id)
            message.context = current.context
            message.status = "awaiting_data"

    try:
        plan, _ = stage(
            "plan", SupervisorPlan, {"question": question, "context": context, "history": history}
        )
        if (
            not plan.agents
            and not plan.missing_fields
            and not re.fullmatch(
                r"(?:oi|olá|ola|bom dia|boa tarde|boa noite|obrigad[oa]|valeu)[!.\s]*",
                question,
                re.I,
            )
        ):
            raise ValueError("Pergunta exige especialista")
        if calculation and "fiscal" not in plan.agents:
            raise ValueError("Cálculo exige diagnóstico fiscal")
        if plan.missing_fields:
            pause(plan.missing_fields)
            return
        legal, fiscal, actions = {"claims": []}, {"claims": []}, {"actions": []}
        support = {}
        # Deterministic fiscal data the interface renders next to the answer.
        published = {}
        if "legal" in plan.agents:
            # Persist tool output separately from LLM claims so a replay uses exactly the same sources.
            def prepare_legal(step):
                passages = tools.legal(question)
                from app.assistant.agents.context import legal_payload

                return legal_payload(question, passages, settings)

            result, legal_step = stage(
                "legal",
                LegalResult,
                {"question": question, "period": context.get("period")},
                prepare_legal,
            )
            support.update(legal_step.tool_result["sources"])
            legal = result.model_dump(mode="json")
        if "fiscal" in plan.agents:
            fiscal_payload = {
                "question": question,
                "period": context.get("period"),
                "calculation": calculation,
            }

            def prepare(step):
                facts = tools.fiscal_status(context.get("period"))
                payload = {
                    "question": question,
                    "facts": facts,
                    "support": {},
                    "period": context.get("period"),
                }
                for scope in ("registration", "federal_certificate", "obligations"):
                    evidence = facts[scope]["latest_evidence"]
                    if evidence:
                        payload["support"]["evidence:" + evidence["id"]] = evidence
                if calculation:
                    computed = tools.calculate(calculation, step.id)
                    payload["support"]["calculation:" + computed["id"]] = computed
                    payload["calculation"] = computed
                return payload

            result, step = stage("fiscal", FiscalResult, fiscal_payload, prepare)
            support.update(step.tool_result["support"])
            published["fiscal_status"] = step.tool_result["facts"]
            if step.tool_result.get("calculation"):
                published["calculation"] = step.tool_result["calculation"]
            fiscal = result.model_dump(mode="json")
            # Required inputs belong to deterministic services, not to model guesses.
            # Evidence lookup can return unverified without any financial inputs.
            if not calculation:
                fiscal["missing_fields"] = []
            else:
                computed = step.tool_result.get("calculation", {})
                fiscal["status"] = (
                    "answered"
                    if computed.get("status") == "calculated"
                    else computed.get("status", "unavailable")
                )
                fiscal["missing_fields"] = []
                if computed.get("status") == "missing_inputs":
                    reason = computed.get("reason", "")
                    fiscal["missing_fields"] = reason.removeprefix("Dados obrigatórios: ").split(
                        ", "
                    )
            if fiscal["missing_fields"]:
                pause(fiscal["missing_fields"])
                return
        # Reject specialist output before the planner sees it.
        for result in (legal, fiscal):
            for claim in result.get("claims", []):
                if not set(claim["support_ids"]).issubset(support):
                    raise ValueError("Fonte inventada pelo especialista")
        if "planning" in plan.agents:
            result, _ = stage(
                "planning", ActionPlan, {"question": question, "legal": legal, "fiscal": fiscal}
            )
            actions = result.model_dump(mode="json")
        result, final_step = stage(
            "synthesis",
            FinalAnswer,
            {"question": question, "legal": legal, "fiscal": fiscal, "actions": actions},
        )
        final = result.model_dump(mode="json")
        if "fiscal" in plan.agents:
            # Validate the text actually published, rather than discarded fiscal prose.
            final["legal_claims"] = legal["claims"]
            final["answer"] = render_answer(final, support, True)
            final["support_ids"] = sorted(
                {
                    ref
                    for result in (legal, fiscal)
                    for claim in result.get("claims", [])
                    for ref in claim["support_ids"]
                }
            )
        validate_results(support, legal, fiscal, actions, final)
        final["legal_claims"] = legal["claims"]
        text = render_answer(final, support, "fiscal" in plan.agents, "legal" in plan.agents)
        with factory.begin() as db:
            current = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if current.revision != revision or current.status != "running":
                raise StaleLease("Execução obsoleta")
            message = db.scalar(
                select(Message).where(
                    Message.operation_id == operation_id, Message.role == "assistant"
                )
            )
            if message is None:
                rendered_refs = set(final["support_ids"])
                if "fiscal" in plan.agents:
                    rendered_refs.update(
                        ref for claim in legal["claims"] for ref in claim["support_ids"]
                    )
                # citation_index keeps the source label equal to the inline [n] of the text.
                citations = [
                    {**value, "citation_index": int(key.split(":", 1)[1])}
                    for key, value in support.items()
                    if key.startswith("legal:") and key in rendered_refs
                ]
                message = Message(
                    conversation_id=user.conversation_id,
                    operation_id=operation_id,
                    role="assistant",
                    text=text,
                    context={**context, **published},
                    citations=citations,
                    next_steps=[action["title"] for action in actions["actions"]],
                    actions=actions["actions"],
                    status="insufficient_context"
                    if "legal" in plan.agents
                    and not legal["claims"]
                    and "fiscal" not in plan.agents
                    else "answered",
                )
                db.add(message)
                db.flush()
            db.get(Message, user.id).status = message.status
            op = db.get(Operation, operation_id)
            op.status, op.error = "succeeded", None
            op.result = {
                "message_id": str(message.id),
                "state": message.status,
                "run_id": str(run_id),
            }
            current.status = "succeeded"
    except JobDeferred:
        with factory.begin() as db:
            db.get(Operation, operation_id).dispatched_at = None
        return
    except StaleLease:
        return
    except Exception:
        with factory.begin() as db:
            current = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if current.revision == revision and current.status != "succeeded":
                current.status = "failed"
                op = db.get(Operation, operation_id)
                op.status, op.error = "failed", "agent_execution_failed"
                db.get(Message, user.id).status = "failed"
