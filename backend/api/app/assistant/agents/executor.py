"""Sequential orchestration; external calls never share a database transaction."""

import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError
from sqlalchemy import select, tuple_

from app.assistant.agents.checkpoints import (
    StaleLease,
    claim_step,
    fail_step,
    fingerprint,
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
from app.assistant.agents.guide_vision import GuideReading, read_guide
from app.assistant.agents.llm import AgentModel
from app.assistant.agents.models import AgentRun, AgentStep
from app.assistant.agents.tools import AgentTools
from app.assistant.agents.validation import render_answer, validate_results
from app.assistant.models import Conversation, Message
from app.companies.service import require_company
from app.config import Settings
from app.errors import DependencyUnavailable
from app.evidence.service import GUIDE_IMAGE_SIGNATURES, require_guide_attachment
from app.jobs.errors import JobDeferred
from app.jobs.models import Operation
from app.legal.ingest import storage_from_settings


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


def _read_stored_guide(settings, evidence, timeout):
    if not settings.guide_vision_available:
        raise DependencyUnavailable("Leitura de guias indisponível")
    storage = storage_from_settings(settings)
    try:
        media_type = storage.content_type(evidence.storage_key, private=True)
        signature = GUIDE_IMAGE_SIGNATURES.get(media_type)
        if signature is None:
            raise ValueError("Formato de guia incompatível")
        image = storage.get(evidence.storage_key, private=True)
    except (BotoCoreError, ClientError):
        raise DependencyUnavailable("Armazenamento indisponível") from None
    if not image.startswith(signature) or hashlib.sha256(image).hexdigest() != evidence.checksum:
        raise ValueError("Imagem da guia inválida")
    return read_guide(settings, image, media_type, timeout=timeout)


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
        request = operation.payload.get("request", {})
        evidence_id = request.get("evidence_id")
        calculation = request.get("calculation")
        if context.get("calculation_input"):
            calculation = context["calculation_input"]
    tools = tools or AgentTools(factory, owner_id, company_id, context, settings)

    def stage(name, schema, payload, prepare=None, *, generate=None):
        step = claim_step(factory, run_id, name, revision, payload, settings)
        if step.status == "succeeded":
            return schema.model_validate(step.result), step
        try:
            actual = step.tool_result
            if actual is None:
                actual = prepare(step) if prepare else payload
                actual = save_tool_result(factory, step.id, step.token, actual)
                step.tool_result = actual
            timeout = min(
                settings.agent_timeout,
                max(1, (step.lease_until - datetime.now(UTC)).total_seconds() - 15),
            )
            if generate is None:
                result, usage = model.generate(name, schema, actual, timeout, settings.num_predict)
            else:
                result, usage = generate(timeout)
            finish_step(factory, step.id, step.token, result.model_dump(mode="json"), usage)
            return result, step
        except (httpx.HTTPError, ConnectionError, TimeoutError, DependencyUnavailable):
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
        reading = None
        period_conflicts = False
        if evidence_id:
            document_input = {"evidence_id": evidence_id}
            with factory() as db:
                evidence = require_guide_attachment(db, owner_id, company_id, UUID(evidence_id))
                previous = db.scalar(
                    select(AgentStep.result).where(
                        AgentStep.run_id == run_id,
                        AgentStep.revision < revision,
                        AgentStep.name == "document",
                        AgentStep.status == "succeeded",
                        AgentStep.input_hash == fingerprint(document_input),
                    )
                )
            if previous is not None:
                reading = GuideReading.model_validate(previous)
            else:
                reading, _ = stage(
                    "document",
                    GuideReading,
                    document_input,
                    generate=lambda timeout: _read_stored_guide(settings, evidence, timeout),
                )
            context["guide_reading"] = {**document_input, **reading.model_dump(mode="json")}
            if reading.period and not context.get("guide_period_confirmed"):
                period_conflicts = bool(
                    context.get("period") and context["period"] != reading.period
                )
                if not context.get("period"):
                    context["period"] = reading.period

        plan, _ = stage(
            "plan", SupervisorPlan, {"question": question, "context": context, "history": history}
        )
        if (
            not plan.agents
            and reading is None
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
        missing_fields = plan.missing_fields
        if reading is not None:
            if context.get("period"):
                missing_fields = [field for field in missing_fields if field != "period"]
            if "fiscal" in plan.agents and (
                period_conflicts
                or (context.get("guide_needs_period") and not context.get("period"))
            ):
                missing_fields = list(dict.fromkeys([*missing_fields, "period"]))
        if missing_fields:
            pause(missing_fields)
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
        if reading is not None and not plan.agents:
            result = FinalAnswer(
                answer=(
                    "Consulte os dados lidos na guia. O pagamento não foi verificado."
                    if any((reading.period, reading.due_date, reading.amount is not None))
                    else "Não consegui ler os campos da guia. Envie uma imagem mais nítida."
                )
            )
        else:
            result, _ = stage(
                "synthesis",
                FinalAnswer,
                {"question": question, "legal": legal, "fiscal": fiscal, "actions": actions},
            )
        final = result.model_dump(mode="json")
        specialist_used = {
            ref
            for specialist in (legal, fiscal)
            for claim in specialist.get("claims", [])
            for ref in claim.get("support_ids", [])
        }

        if "legal" in plan.agents and not legal.get("claims") and "fiscal" not in plan.agents:
            # Legal context insufficient: reject invented synthesis claims
            final["legal_claims"] = []
            final["support_ids"] = []
            final["answer"] = render_answer(final, support, False, True)
        elif "fiscal" in plan.agents:
            # Validate the text actually published, rather than discarded fiscal prose.
            final["legal_claims"] = legal["claims"]
            final["answer"] = render_answer(final, support, True, "legal" in plan.agents)
            final["support_ids"] = sorted(
                {
                    ref
                    for res in (legal, fiscal)
                    for claim in res.get("claims", [])
                    for ref in claim["support_ids"]
                }
            )
        else:
            final["legal_claims"] = legal.get("claims", [])
            synthesis_refs = [ref for ref in final.get("support_ids", []) if ref in specialist_used]
            legal_refs = sorted(
                {
                    ref
                    for claim in legal.get("claims", [])
                    for ref in claim.get("support_ids", [])
                    if ref.startswith("legal:")
                }
            )
            final["support_ids"] = sorted(set(synthesis_refs) | set(legal_refs))
            final["answer"] = render_answer(final, support, False, "legal" in plan.agents)

        try:
            validate_results(support, legal, fiscal, actions, final)
        except ValueError as err:
            if "Síntese sem suporte" in str(err) and "legal" in plan.agents:
                final["legal_claims"] = []
                final["support_ids"] = []
                final["answer"] = (
                    "Não encontrei contexto normativo publicado e vigente suficiente para responder."
                )
            else:
                raise

        final["legal_claims"] = legal.get("claims", [])
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
