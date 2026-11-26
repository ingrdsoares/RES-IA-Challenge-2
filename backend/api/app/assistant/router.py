from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.models import Account
from app.assistant.models import Conversation, Message
from app.assistant.schemas import (
    ConversationInput,
    ConversationPatch,
    ConversationView,
    GuideOption,
    GuideOptionsView,
    MessageInput,
    MessageView,
)
from app.assistant.service import require_conversation, submit_message
from app.companies.service import require_company
from app.db import get_db
from app.dependencies import require_account
from app.evidence.models import Evidence
from app.evidence.service import (
    ASSISTANT_DOCUMENT_KINDS,
    assistant_document_supported,
    guide_attachment_media_type,
)
from app.legal.ingest import storage_from_settings
from app.pagination import page
from app.rate_limit import RateLimiter

router = APIRouter(tags=["Assistente"])


@router.post("/empresas/{company_id}/conversas", response_model=ConversationView, status_code=201)
def create(
    company_id: UUID,
    data: ConversationInput,
    db: Session = Depends(get_db),
    account: Account = Depends(require_account),
):
    require_company(db, account.id, company_id)
    conversation = Conversation(company_id=company_id, title=data.title)
    db.add(conversation)
    db.commit()
    return conversation


@router.get("/empresas/{company_id}/conversas")
def conversations(
    company_id: UUID,
    include_archived: bool = False,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    account: Account = Depends(require_account),
):
    require_company(db, account.id, company_id)
    query = select(Conversation).where(Conversation.company_id == company_id)
    if not include_archived:
        query = query.where(Conversation.archived_at.is_(None))
    return page(
        db,
        query,
        Conversation,
        ConversationView,
        limit,
        cursor,
    )


@router.get("/empresas/{company_id}/guias-para-assistente", response_model=GuideOptionsView)
def guide_options(
    company_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    account: Account = Depends(require_account),
):
    require_company(db, account.id, company_id)
    settings = request.app.state.settings
    vision = settings.guide_vision_available
    # Declarations are read locally, so they stay available when image reading is off.
    kinds = ASSISTANT_DOCUMENT_KINDS if vision else ("declaration",)
    candidates = page(
        db,
        select(Evidence).where(
            Evidence.company_id == company_id,
            Evidence.kind.in_(kinds),
            Evidence.storage_key.is_not(None),
        ),
        Evidence,
        lambda row: row,
        limit,
        cursor,
    )
    storage = storage_from_settings(settings)
    items = []
    for row in candidates["items"]:
        media_type = guide_attachment_media_type(storage, row.storage_key)
        if assistant_document_supported(row.kind, media_type, vision):
            items.append(
                GuideOption(
                    id=row.id,
                    period=row.period,
                    created_at=row.created_at,
                    kind=row.kind,
                    media_type=media_type,
                )
            )
    return GuideOptionsView(enabled=vision, items=items, next_cursor=candidates["next_cursor"])


@router.get("/conversas/{conversation_id}", response_model=ConversationView)
def get(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    account: Account = Depends(require_account),
):
    return require_conversation(db, account.id, conversation_id)[0]


@router.patch("/conversas/{conversation_id}", response_model=ConversationView)
def patch(
    conversation_id: UUID,
    data: ConversationPatch,
    db: Session = Depends(get_db),
    account: Account = Depends(require_account),
):
    conversation = require_conversation(db, account.id, conversation_id, lock=True)[0]
    if "title" in data.model_fields_set:
        conversation.title = data.title
    if "archived" in data.model_fields_set:
        conversation.archived_at = datetime.now(UTC) if data.archived else None
    db.commit()
    return conversation


@router.get("/conversas/{conversation_id}/mensagens")
def messages(
    conversation_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    account: Account = Depends(require_account),
):
    require_conversation(db, account.id, conversation_id)
    return page(
        db,
        select(Message).where(Message.conversation_id == conversation_id),
        Message,
        MessageView,
        limit,
        cursor,
    )


@router.post(
    "/conversas/{conversation_id}/mensagens",
    status_code=202,
    dependencies=[Depends(RateLimiter(namespace="ai_rag"))],
)
def send(
    conversation_id: UUID,
    data: MessageInput,
    request: Request,
    idempotency_key: str = Header(..., min_length=1, max_length=128),
    db: Session = Depends(get_db),
    account: Account = Depends(require_account),
):
    operation = submit_message(
        db, account.id, conversation_id, data, idempotency_key, settings=request.app.state.settings
    )
    from app.assistant.agents.models import AgentRun

    run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation.id))
    db.commit()
    return {
        "run_id": run.id if run else None,
        "trace_id": run.trace_id if run else None,
        "operation_id": operation.id,
        "status": operation.status,
        "status_url": f"/operacoes/{operation.id}",
        "missing_fields": (operation.result or {}).get("missing_fields", []),
    }
