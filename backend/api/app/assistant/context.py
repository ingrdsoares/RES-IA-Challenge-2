import re

from fastapi import HTTPException

from app.assistant.extractor import TaxEntityExtractor
from app.assistant.schemas import ContextDecision, MessageInput
from app.companies.schemas import CompanySnapshot


def resolve_context(snapshot: CompanySnapshot, message: MessageInput) -> ContextDecision:
    context = {"company": snapshot.model_dump(mode="json")}
    missing = []

    extractor = TaxEntityExtractor()
    extraction = extractor.extract(message.text)
    context["extraction"] = extraction.to_dict()
    if extraction.query_expandida:
        context["query_expandida"] = extraction.query_expandida
    if extraction.parametros_calculo:
        context["extracted_parameters"] = extraction.parametros_calculo

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
    requires_period = bool(
        re.search(
            r"\bpaguei\b|\bpagamento\b|\bcompet[eê]ncia\b|\b(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
            message.text,
            re.I,
        )
    ) or (
        bool(re.search(r"quanto|calcul|apur|venc", message.text, re.I))
        and not bool(
            re.search(
                r"\b(qual\s+(o|a)\s+(data|dia|prazo|vencimento)|quanto\s+(o\s+)?mei|como\s+calcular|tabela|al[ií]quota|regra)\b|\bmei\b|\bsimei\b",
                message.text,
                re.I,
            )
        )
    )
    if requires_period and "period" not in context:
        missing.append("period")
    if re.search(r"\bsou\s+mei\b", message.text, re.I) and snapshot.regime.casefold() not in (
        "mei",
        "simei",
    ):
        missing.append("regime")
    return ContextDecision(
        state="awaiting_data" if missing else "ready", context=context, missing_fields=missing
    )
