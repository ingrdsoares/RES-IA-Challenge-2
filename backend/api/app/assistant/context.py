import re

from fastapi import HTTPException

from app.assistant.schemas import ContextDecision, MessageInput
from app.companies.schemas import CompanySnapshot


def resolve_context(snapshot: CompanySnapshot, message: MessageInput) -> ContextDecision:
    context = {"company": snapshot.model_dump(mode="json")}
    missing = []
    period = re.search(r"\b([0-9]{4})-(0[1-9]|1[0-2])\b", message.text)
    reverse = re.search(r"\b(0[1-9]|1[0-2])/([0-9]{4})\b", message.text)
    if period:
        context["period"] = period.group(0)
    elif reverse:
        context["period"] = f"{reverse[2]}-{reverse[1]}"
    if message.calculation:
        if context.get("period") and context["period"] != message.calculation.period:
            raise HTTPException(422, "Competência do cálculo diverge da mensagem")
        context["period"] = message.calculation.period
    if (
        re.search(r"paguei|pagamento|quanto|calcul|apur|venc|compet[eê]ncia", message.text, re.I)
        and "period" not in context
    ):
        missing.append("period")
    if re.search(r"\bsou\s+mei\b", message.text, re.I) and snapshot.regime.casefold() not in (
        "mei",
        "simei",
    ):
        missing.append("regime")
    return ContextDecision(
        state="awaiting_data" if missing else "ready", context=context, missing_fields=missing
    )
