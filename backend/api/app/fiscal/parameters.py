from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.fiscal.schemas import Money

Rate = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False, max_digits=12, decimal_places=10)]


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def exact_numbers(cls, value):
        def check(item):
            if isinstance(item, float):
                raise ValueError("Parâmetros decimais devem ser strings")
            if isinstance(item, dict):
                for child in item.values():
                    check(child)
            if isinstance(item, list):
                for child in item:
                    check(child)

        check(value)
        return value


class MeiParameters(Parameters):
    salary: Money
    inss_rate: Rate
    icms: Money
    iss: Money
    activities: dict[str, Literal["trade", "services", "mixed"]]
    limitations: list[str] = Field(min_length=1)


class Band(Parameters):
    upper: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]
    rate: Rate
    deduction: Money
    shares: dict[str, Rate]

    @model_validator(mode="after")
    def shares_sum(self):
        if self.shares and sum(self.shares.values(), Decimal(0)) != Decimal(1):
            raise ValueError("Repartição deve somar 1")
        return self


class Activity(Parameters):
    annex: Literal["I", "II", "III", "IV", "V"]
    factor_r: bool


class SimplesParameters(Parameters):
    activities: dict[str, Activity]
    factor_r_threshold: Rate
    rate_places: int = Field(ge=4, le=10)
    annexes: dict[Literal["I", "II", "III", "IV", "V"], list[Band]]
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def bands_ordered(self):
        for bands in self.annexes.values():
            if not bands or any(a.upper >= b.upper for a, b in zip(bands, bands[1:])):
                raise ValueError("Faixas devem estar ordenadas e sem limites repetidos")
        for activity in self.activities.values():
            required = {"III", "V"} if activity.factor_r else {activity.annex}
            if not required.issubset(self.annexes):
                raise ValueError("Anexos ausentes")
        return self


def validate_parameters(kind, data):
    return (MeiParameters if kind == "mei" else SimplesParameters).model_validate(data)
