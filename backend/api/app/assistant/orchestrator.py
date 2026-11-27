import json
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from qdrant_client import QdrantClient
from sqlalchemy import select, tuple_

from app.assistant.citations import validate_answer_citations
from app.assistant.models import Conversation, Message
from app.assistant.stages import diagnose, plan_steps, stage, supervise
from app.assistant.tools import retrieve_legal
from app.config import Settings
from app.fiscal.schemas import CalculationInput
from app.fiscal.service import calculate
from app.jobs.errors import JobDeferred
from app.jobs.models import Operation
from app.llm_client import chat
from app.models import LocalModels
from app.prompt_management import load_prompt, traced
from app.serialization import record


class AssistantDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]
    cited_indices: list[int] = Field(max_length=10)
    next_steps: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    ] = Field(max_length=3)


@traced("assistant.legacy")
def answer_message(db, operation, *, settings=None, index=None, embed=None, generate=None):
    if operation.status == "awaiting_data":
        return {"state": "awaiting_data"}
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.id == UUID(operation.payload["conversation_id"]))
        .with_for_update()
    )
    user = db.scalar(
        select(Message).where(Message.operation_id == operation.id, Message.role == "user")
    )
    if user is None or conversation is None or conversation.company_id != operation.company_id:
        raise ValueError("Contexto de conversa inválido")
    prior = db.scalar(
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
    if prior:
        raise JobDeferred()
    existing = db.scalar(
        select(Message).where(Message.operation_id == operation.id, Message.role == "assistant")
    )
    if existing:
        return {"message_id": str(existing.id), "state": existing.status}
    checkpoint = (operation.result or {}).get("checkpoint", {}).copy()
    trace = list((operation.result or {}).get("stages", []))

    fraude_termos = [
        "sonegar",
        "sonegação",
        "esconder receita",
        "nota calçada",
        "fraudar",
        "fraude",
        "lavagem de dinheiro",
        "crime fiscal",
        "laranja",
        "laranjas",
        "vários meis",
        "interposição de pessoas",
        "paraíso fiscal",
    ]
    user_text_lower = user.text.lower()
    if any(termo in user_text_lower for termo in fraude_termos):
        answer = (
            "Esta solicitação ultrapassa o escopo de atuação do Sócio Digital para orientações "
            "ordinárias de MEI e Simples Nacional. O Sócio Digital atua em conformidade estrita "
            "com as diretrizes éticas e legais (Resolução CFC nº 803/1996 e CRC), abstendo-se "
            "de qualquer orientação contrária à legislação tributária."
        )
        steps = [
            "Interromper qualquer ação sem fundamentação formal expressa.",
            "Agendar atendimento com escritório contábil habilitado (CRC).",
            "Buscar assessoria jurídica especializada em Direito Tributário se necessário.",
        ]
        reply = Message(
            conversation_id=conversation.id,
            operation_id=operation.id,
            role="assistant",
            text=answer,
            context=user.context,
            citations=[],
            next_steps=steps,
            status="answered",
        )
        db.add(reply)
        user.status = "answered"
        db.flush()
        return {"message_id": str(reply.id), "state": "answered"}
    calculation_input = operation.payload.get("request", {}).get("calculation")
    with stage(trace, "supervisor", checkpoint):
        route = supervise(user.text, bool(calculation_input))
    facts = None
    if route.diagnosis:
        with stage(trace, "diagnostico_fiscal", checkpoint):
            facts = checkpoint.get("fiscal_status")
            if facts is None:
                facts = diagnose(db, operation.company_id, user.context.get("period")).model_dump()
                checkpoint["fiscal_status"] = facts
            user.context = {**user.context, "fiscal_status": facts}
    if route.calculation:
        with stage(trace, "calculo", checkpoint):
            calculation = calculate(
                db,
                operation.company_id,
                operation.owner_id,
                CalculationInput.model_validate(calculation_input),
                context_snapshot=user.context["company"],
            )
        user.context = {**user.context, "calculation": record(calculation)}
        if calculation.status == "calculated":
            answer = f"Valor simulado pelo motor: R$ {calculation.result['amount']}. Regra: {calculation.result['rule_version']}. Esta simulação não confirma pagamento nem regularidade."
        else:
            answer = calculation.reason
        reply = Message(
            conversation_id=conversation.id,
            operation_id=operation.id,
            role="assistant",
            text=answer,
            context=user.context,
            citations=[],
            next_steps=[],
            status=calculation.status,
        )
        db.add(reply)
        user.status = calculation.status
        db.flush()
        return {
            "message_id": str(reply.id),
            "state": calculation.status,
            "calculation_id": str(calculation.id),
            "stages": trace,
        }
    settings = settings or Settings()
    own_index, own_models = index is None, embed is None
    index = (
        index
        if index is not None
        else QdrantClient(url=str(settings.qdrant_url), timeout=settings.qdrant_timeout)
    )
    model = LocalModels(settings) if own_models else None
    try:
        with stage(trace, "juridico", checkpoint):
            search_query = user.context.get("query_expandida") or user.text
            passages = retrieve_legal(
                db,
                index,
                search_query,
                user.context,
                embed or model.embed_question,
                settings.top_k,
                settings.score_threshold,
            )
        citations, steps = [], []
        if not passages:
            answer = "Não encontrei contexto normativo publicado e vigente suficiente para responder. A situação fiscal da empresa permanece não verificada."
            if facts and any(
                facts[scope]["latest_evidence"]
                for scope in ("registration", "federal_certificate", "obligations")
            ):
                answer = "Não encontrei norma vigente suficiente. Há evidências declaradas registradas para este contexto. Elas não comprovam pagamento nem regularidade fiscal. Verificação oficial: não realizada."
                state = "answered"
            else:
                state = "insufficient_context"
        else:
            with stage(trace, "sintese", checkpoint):
                draft, citations = synthesize(
                    db, user, conversation, passages, settings, model, generate
                )
                answer, steps, state = draft.answer, draft.next_steps, "answered"
        with stage(trace, "planejamento", checkpoint):
            steps = plan_steps(citations, route.diagnosis, steps)
        if route.diagnosis and citations:
            answer += "\n\nVerificação oficial de pagamento: não realizada."
        message = Message(
            conversation_id=conversation.id,
            operation_id=operation.id,
            role="assistant",
            text=answer,
            context=user.context,
            citations=citations,
            next_steps=steps,
            status=state,
        )
        db.add(message)
        user.status = state
        db.flush()
        return {"message_id": str(message.id), "state": state, "stages": trace}
    finally:
        if own_index:
            index.close()
        if own_models:
            model.close()


def synthesize(db, user, conversation, passages, settings, model, generate):
    for citation_index, passage in enumerate(passages, start=1):
        passage["citation_index"] = citation_index
    history = list(
        db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                tuple_(Message.created_at, Message.id) < tuple_(user.created_at, user.id),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(6)
        )
    )
    content = {
        "question": user.text,
        "context": user.context,
        "history": [{"role": item.role, "text": item.text[:2000]} for item in reversed(history)],
        "passages": passages,
    }
    prompt = load_prompt("assistant/legacy") if generate is None else None
    budget = settings.num_ctx - settings.num_predict - 512
    prompt_bytes = len(prompt.text.encode()) if prompt else 0
    while len(json.dumps(content, ensure_ascii=False).encode()) + prompt_bytes > budget:
        if content["history"]:
            content["history"].pop(0)
        elif len(passages) > 1:
            passages.pop()
        elif len(passages[0]["text"]) > 256:
            passages[0]["text"] = passages[0]["text"][: len(passages[0]["text"]) // 2]
        else:
            raise ValueError("Contexto excede orçamento")
    if generate:
        draft = AssistantDraft.model_validate(generate(content))
    else:
        response = chat(
            settings,
            [
                {"role": "system", "content": prompt.text},
                {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
            ],
            prompt=prompt,
            max_tokens=settings.num_predict,
            schema=transport_schema(),
            ollama_client=model.client if model else None,
            http_client=model.http_client if model else None,
        )
        draft = AssistantDraft.model_validate_json(response.texto)
    citations = validate_answer_citations(draft.answer, draft.cited_indices, passages)
    return draft, citations


def transport_schema():
    # Large bounded repetitions are not supported by every local grammar sampler.
    # Keep the transport grammar small; AssistantDraft enforces all bounds afterwards.
    def simplify(value):
        if isinstance(value, dict):
            return {
                key: simplify(item)
                for key, item in value.items()
                if key not in {"title", "minLength", "maxLength", "minItems", "maxItems"}
            }
        if isinstance(value, list):
            return [simplify(item) for item in value]
        return value

    return simplify(AssistantDraft.model_json_schema())
