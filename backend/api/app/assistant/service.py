from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.assistant.context import resolve_context
from app.assistant.models import Conversation, Message
from app.assistant.schemas import MessageInput
from app.companies.service import require_company, snapshot
from app.jobs.models import Operation
from app.jobs.service import enqueue


def require_conversation(db, account_id, conversation_id, lock=False):
    query = select(Conversation).where(Conversation.id == conversation_id)
    if lock:
        query = query.with_for_update()
    conversation = db.scalar(query)
    if conversation is None:
        raise HTTPException(404, "Conversa não encontrada")
    company = require_company(db, account_id, conversation.company_id)
    return conversation, company


def submit_message(
    db, account_id: UUID, conversation_id: UUID, request: MessageInput, key: str
) -> Operation:
    conversation, company = require_conversation(db, account_id, conversation_id, lock=True)
    # Immutable request body is the idempotency fingerprint, including conversation scope.
    payload = {"conversation_id": str(conversation.id), "request": request.model_dump(mode="json")}
    receipt = enqueue(
        db,
        "assistant.confirm" if request.confirmation_for else "assistant.answer",
        account_id,
        company.id,
        key,
        payload,
    )
    existing = db.scalar(
        select(Message).where(Message.operation_id == receipt.id, Message.role == "user")
    )
    if existing:
        if request.confirmation_for:
            return db.get(Operation, request.confirmation_for)
        return receipt
    if request.confirmation_for:
        operation = db.get(Operation, request.confirmation_for)
        if not operation or operation.owner_id != account_id or operation.company_id != company.id:
            raise HTTPException(404, "Operação não encontrada")
        original = db.scalar(
            select(Message).where(Message.operation_id == operation.id, Message.role == "user")
        )
        if not original or original.conversation_id != conversation.id:
            raise HTTPException(404, "Operação não encontrada")
        if operation.status != "awaiting_data" or request.confirmation is None:
            raise HTTPException(409, "Operação não aguarda esta confirmação")
        values = request.confirmation.model_dump(exclude_none=True)
        missing = original.context.get("missing_fields", [])
        if set(values) != set(missing):
            raise HTTPException(422, "Confirme somente os campos solicitados")
        context = {**original.context, **values, "missing_fields": []}
        original.context = context
        original.status = "queued"
        operation.status = "queued"
        operation.result = None
        operation.dispatched_at = None
        receipt.status = "succeeded"
        receipt.result = {"operation_id": str(operation.id)}
    else:
        if request.confirmation:
            raise HTTPException(422, "Confirmação exige operação de origem")
        operation = receipt
        decision = resolve_context(snapshot(company), request)
        context = {**decision.context, "missing_fields": decision.missing_fields}
        operation.status = "awaiting_data" if decision.missing_fields else "queued"
        if decision.missing_fields:
            operation.result = {"missing_fields": decision.missing_fields}
    db.add(
        Message(
            id=uuid4(),
            conversation_id=conversation.id,
            operation_id=receipt.id,
            role="user",
            text=request.text,
            context=context,
            status=receipt.status,
        )
    )
    db.flush()
    return operation
