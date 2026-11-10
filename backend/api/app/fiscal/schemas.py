from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

Period = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]


class RuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["mei", "simples"]
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    valid_from: Period
    valid_to: Period
    parameters: dict
    references: list[HttpUrl] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def dates(self):
        if self.valid_to < self.valid_from:
            raise ValueError("Intervalo inválido")
        return self


class CalculationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["mei", "simples"]
    period: Period
    rbt12: Money | None = None
    revenue: Money | None = None
    payroll12: Money | None = None
    activity: Literal["trade", "services", "mixed"] | None = None
    conditions_confirmed: bool = False

    @field_validator("rbt12", "revenue", "payroll12", mode="before")
    @classmethod
    def decimal_strings(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("Use strings decimais para valores monetários")
        return value
