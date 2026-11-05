import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class Source(BaseModel):
    id: int | str
    text: NonEmpty
    source: Annotated[NonEmpty, Field(max_length=2048)]
    score: float = Field(allow_inf_nan=False)
    title: Annotated[str, Field(max_length=256)] | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    reference_date: date | None = None
    effective_date: date | None = None

    @field_validator("reference_date", "effective_date", mode="before")
    @classmethod
    def require_iso_date(cls, value):
        if value is None:
            return None
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Dates must use YYYY-MM-DD strings")
        return date.fromisoformat(value)


class QueryResponse(BaseModel):
    status: Literal["answered", "empty_knowledge_base", "insufficient_context"]
    answer: str
    sources: list[Source]
