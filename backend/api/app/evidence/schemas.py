from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Period = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]


class ObligationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Text
    period: Period | None = None
    due_date: date | None = None


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["guide", "payment", "declaration", "certificate", "registration", "other"]
    scope: Literal["registration", "federal_certificate", "obligations"]
    period: Period | None = None
    obligation_id: UUID | None = None
    valid_until: date | None = None
