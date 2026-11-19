from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
SupportId = Annotated[
    str, StringConstraints(pattern=r"^(legal|evidence|calculation):[A-Za-z0-9_-]+$")
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


MissingField = Literal[
    "period", "regime", "kind", "revenue", "rbt12", "payroll12", "activity", "conditions_confirmed"
]


class SupervisorPlan(Contract):
    intent: Text
    agents: list[Literal["legal", "fiscal", "planning"]] = Field(default_factory=list, max_length=3)
    missing_fields: list[MissingField] = Field(default_factory=list, max_length=8)
    reason: Text = "Contexto da solicitação"

    @model_validator(mode="after")
    def dependencies(self):
        if len(set(self.agents)) != len(self.agents):
            raise ValueError("Especialistas duplicados")
        if self.agents == ["planning"]:
            raise ValueError("Planejamento exige especialista de suporte")
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("Campos duplicados")
        return self


class Claim(Contract):
    text: Text
    support_ids: list[SupportId] = Field(min_length=1, max_length=10)


class LegalResult(Contract):
    status: Literal["answered", "insufficient_context", "unavailable"]
    claims: list[Claim] = Field(default_factory=list, max_length=10)
    limitations: list[Text] = Field(default_factory=list, max_length=5)


class FiscalResult(Contract):
    status: Literal[
        "answered", "missing_inputs", "rule_unavailable", "unsupported_case", "unavailable"
    ]
    claims: list[Claim] = Field(default_factory=list, max_length=10)
    missing_fields: list[MissingField] = Field(default_factory=list, max_length=8)
    limitations: list[Text] = Field(default_factory=list, max_length=5)


class Action(Contract):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    priority: Literal["high", "normal", "low"] = "normal"
    preconditions: list[Text] = Field(default_factory=list, max_length=5)
    support_ids: list[SupportId] = Field(min_length=1, max_length=10)
    responsible: Text | None = None
    due_date: date | None = None
    deadline_kind: Literal["suggested", "normative"] = "suggested"


class ActionPlan(Contract):
    actions: list[Action] = Field(default_factory=list, max_length=3)


class FinalAnswer(Contract):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]
    support_ids: list[SupportId] = Field(default_factory=list, max_length=30)
