from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.evidence.schemas import Period


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
        | None
    ) = None
    period: Period | None = None
    due_date: date | None = None
    source_message_id: UUID | None = None
    source_step_index: int | None = Field(None, ge=0, le=2)


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed: bool
