from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.fiscal.schemas import CalculationInput

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Period = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]


class ConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ] = "Nova conversa"


class ContextConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: Period | None = None
    regime: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)] | None
    ) = None


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Text
    calculation: CalculationInput | None = None
    confirmation_for: UUID | None = None
    confirmation: ContextConfirmation | None = None


class ConversationView(ConversationInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    created_at: datetime


class MessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    operation_id: UUID | None
    role: str
    text: str
    context: dict
    citations: list
    next_steps: list
    status: str
    created_at: datetime


class ContextDecision(BaseModel):
    state: str
    context: dict
    missing_fields: list[str] = Field(default_factory=list)
