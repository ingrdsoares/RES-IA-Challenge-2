"""Routing and deterministic tools for the company assistant."""

import re
from contextlib import contextmanager
from time import monotonic
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.evidence.service import get_fiscal_status
from app.jobs.errors import AssistantStageFailed


class Indicator(BaseModel):
    verification: Literal["unverified"]
    evidence_state: Literal["absent", "expired", "declared"]
    latest_evidence: dict | None


class FiscalDiagnosis(BaseModel):
    coverage: Literal["partial"]
    registration: Indicator
    federal_certificate: Indicator
    obligations: Indicator


class Route(BaseModel):
    diagnosis: bool
    calculation: bool


def supervise(question: str, calculation: bool) -> Route:
    fiscal = re.search(
        r"paguei|pagamento|pago|quitei|débito|d[ií]vida|regular|pend[eê]n|"
        r"situa[çc][aã]o|certid[aã]o|comprovante|evid[eê]ncia|minha (empresa|guia)|"
        r"obriga[çc][oõ]|quanto devo",
        question,
        re.I,
    )
    return Route(diagnosis=calculation or bool(fiscal), calculation=calculation)


def diagnose(db, company_id: UUID, period: str | None) -> FiscalDiagnosis:
    return FiscalDiagnosis.model_validate(get_fiscal_status(db, company_id, period))


def plan_steps(citations: list, fiscal: bool, suggestions: list[str]) -> list[str]:
    steps = []
    if fiscal:
        steps.append("Conferir o comprovante da competência consultada.")
    if citations:
        steps.extend(suggestions or ["Consultar o trecho citado da norma."])
    return list(dict.fromkeys(steps))[:3]


@contextmanager
def stage(trace, name, checkpoint):
    started = monotonic()
    entry = {"role": name, "status": "running"}
    trace.append(entry)
    try:
        yield
    except Exception as exc:
        entry["status"] = "failed"
        raise AssistantStageFailed(trace, checkpoint) from exc
    else:
        entry["status"] = "succeeded"
    finally:
        entry["duration_ms"] = round((monotonic() - started) * 1000)
