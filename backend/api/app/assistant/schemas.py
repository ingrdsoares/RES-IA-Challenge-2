from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.fiscal.schemas import CalculationInput, Money

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Period = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]


class ConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ] = "Nova conversa"


class ConversationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ] = ""
    archived: StrictBool = False

    @model_validator(mode="after")
    def something_to_change(self):
        if not self.model_fields_set:
            raise ValueError("Informe o que alterar")
        return self


class ContextConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["mei", "simples"] | None = None
    revenue: Money | None = None
    rbt12: Money | None = None
    payroll12: Money | None = None
    activity: Literal["trade", "services", "mixed"] | None = None
    conditions_confirmed: StrictBool | None = None

    @field_validator("revenue", "rbt12", "payroll12", mode="before")
    @classmethod
    def decimal_inputs(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("Use strings decimais")
        return value

    period: Period | None = None
    regime: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)] | None
    ) = None


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Text
    calculation: CalculationInput | None = None
    evidence_id: UUID | None = None
    confirmation_for: UUID | None = None
    confirmation: ContextConfirmation | None = None


class GuideOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    period: Period | None
    created_at: datetime
    kind: Literal["guide", "declaration"]
    media_type: str


class GuideOptionsView(BaseModel):
    enabled: bool
    items: list[GuideOption]
    next_cursor: str | None


class ConversationView(ConversationInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    archived_at: datetime | None
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
    actions: list = Field(default_factory=list)
    next_steps: list
    status: str
    created_at: datetime


class ContextDecision(BaseModel):
    state: str
    context: dict
    missing_fields: list[str] = Field(default_factory=list)
