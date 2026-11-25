from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from time import monotonic
from typing import Literal

from pydantic import field_serializer

from app.assistant.agents.contracts import Contract
from app.assistant.multimodal.pdf_parser import MultimodalPDFParser
from app.fiscal.schemas import Money

PARSER = "dasn-pdf-parser"
PARSER_VERSION = "dasn-v1"
CENT = Decimal("0.01")


class DeclarationReading(Contract):
    """Validated DASN-SIMEI fields read locally from a PDF; no external call."""

    legible: bool
    ano_calendario: int | None = None
    cnpj: str | None = None
    razao_social: str | None = None
    receita_total: Money | None = None
    limite_anual: Money | None = None
    excesso_valor: Money | None = None
    excesso_percentual: Decimal | None = None
    faixa_excesso: Literal["dentro_do_limite", "ate_20_porcento", "acima_20_porcento"] | None = None
    efeito_enquadramento: str | None = None
    data_efeito: date | None = None
    fundamentacao_legal: str | None = None

    @field_serializer(
        "receita_total", "limite_anual", "excesso_valor", "excesso_percentual", when_used="json"
    )
    def two_places(self, value):
        return format(value, ".2f") if value is not None else None


def _cents(value: float) -> Decimal:
    # The parser computes in float; money leaves this module as exact cents.
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def read_declaration(pdf: bytes) -> tuple[DeclarationReading, dict]:
    started = monotonic()
    result = MultimodalPDFParser().parse(pdf)
    if result.document_type != "DASN-SIMEI" or result.ano_calendario is None:
        reading = DeclarationReading(legible=False)
    else:
        reading = DeclarationReading(
            legible=True,
            ano_calendario=result.ano_calendario,
            cnpj=result.cnpj,
            razao_social=result.razao_social,
            receita_total=_cents(result.receita_total),
            limite_anual=_cents(result.limite_anual),
            excesso_valor=_cents(result.excesso_valor),
            excesso_percentual=_cents(result.excesso_percentual),
            faixa_excesso=result.faixa_excesso,
            efeito_enquadramento=result.efeito_enquadramento,
            data_efeito=result.data_efeito,
            fundamentacao_legal=result.fundamentacao_legal,
        )
    return reading, {
        "model": PARSER,
        "prompt_version": PARSER_VERSION,
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": round((monotonic() - started) * 1000),
        "monetary_cost": None,
    }
