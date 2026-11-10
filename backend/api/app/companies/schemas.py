import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CompanyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cnpj: str
    cnae: Annotated[str, StringConstraints(pattern=r"^\d{7}$")]
    size: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    regime: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    municipality: Text
    state: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]

    @field_validator("cnpj")
    @classmethod
    def validate_cnpj(cls, value):
        value = re.sub(r"[./\-\s]", "", value)
        if not re.fullmatch(r"\d{14}", value) or len(set(value)) == 1:
            raise ValueError("CNPJ inválido")
        for length, weights in (
            (12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
            (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
        ):
            remainder = sum(int(v) * w for v, w in zip(value[:length], weights)) % 11
            if int(value[length]) != (0 if remainder < 2 else 11 - remainder):
                raise ValueError("CNPJ inválido")
        return value


class CompanyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cnae: Annotated[str, StringConstraints(pattern=r"^\d{7}$")] | None = None
    size: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] | None
    ) = None
    regime: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)] | None
    ) = None
    municipality: Text | None = None
    state: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")] | None = None


class CompanyView(CompanyInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provenance: dict
    created_at: datetime


class CompanySnapshot(CompanyView):
    pass
