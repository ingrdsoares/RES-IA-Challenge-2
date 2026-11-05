from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


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


class QueryResponse(BaseModel):
    status: Literal["answered", "empty_knowledge_base", "insufficient_context"]
    answer: str
    sources: list[Source]
