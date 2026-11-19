import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value


class Credentials(EmailInput):
    password: Password


class NewPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    password: Password


class AccountView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
