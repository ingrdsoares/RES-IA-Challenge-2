import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: Annotated[str, StringConstraints(min_length=12, max_length=128)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value


class AccountView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
