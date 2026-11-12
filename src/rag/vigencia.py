"""Data do ato (publicação ou edição) para a coluna vigencia_fonte / payload effective_date.

Semântica: é a data em que o ato foi editado/publicado na fonte, NÃO o início da vigência
(vacatio legis, produção de efeitos diferida e prorrogações não são inferidos). Serve para
ordenar: de dois atos sobre o mesmo assunto, o de data maior é o mais novo.

Texto consolidado fica sem data: o texto reflete emendas posteriores, então a data do ato
original seria a de uma redação que o texto não tem (ex.: Lei 1.254/1996 do DF com a alíquota
alterada para 20% em 2024). Prefere-se correção a cobertura: na dúvida, None.
"""

import re
from datetime import date

_MESES = {
    m: i
    for i, m in enumerate(
        "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro".split(),
        1,
    )
}
# Só ", de DD de mês [de] AAAA" (a data do próprio ato, não a de uma norma citada no título).
# "de" antes do ano é opcional: o SINJ-DF traz "DE 03 DE JANEIRO 2005".
_TITULO = re.compile(
    r",\s*de\s+(\d{1,2})\s*[ºo°]?\s+de\s+([A-Za-zÀ-ú]+)\s+(?:de\s+)?(\d{4})", re.IGNORECASE
)
_DODF = re.compile(
    r"PUBLICAD[AO]\s+NO\s+DODF\s+N[^\d]{0,4}\d+[^\n]{0,20}?,\s*DE\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
# Marcas de texto consolidado: redação dada, inclusões/revogações anotadas, visão multivigente.
_CONSOLIDADO = re.compile(
    r"Reda[çc][ãa]o dada pel|\((?:Inclu[ií]d|Revogad|Vide|Renumerad|Acrescid)[oa]s? pel"
    r"|(?:alterad|acrescid|revogad|inclu[ií]d)o\(a\) pel|retornada multivigente",
    re.IGNORECASE,
)
# Atos de interpretação não são emendados: "Vide"/"Redação dada" no corpo é citação, não consolidação.
NATUREZAS_NAO_CONSOLIDAVEIS = frozenset(
    {"interpretacao_administrativa", "consulta_tributaria", "orientacao_oficial"}
)


def _iso(ano: int, mes: int, dia: int) -> str | None:
    try:
        return date(ano, mes, dia).isoformat()
    except ValueError:
        return None


def data_iso_br(valor: str | None) -> str | None:
    """AAAA-MM-DD a partir de "AAAA-MM-DD..." ou "DD/MM/AAAA"; None se vazio ou inválido."""
    valor = (valor or "").strip()
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?", valor):
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    if m := re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", valor):
        return _iso(int(m[3]), int(m[2]), int(m[1]))
    return None


def data_do_titulo(titulo: str | None) -> str | None:
    """Primeira ocorrência de ", de 3 de janeiro de 2005" no título, em ISO; None se não houver."""
    for m in _TITULO.finditer(titulo or ""):
        mes = _MESES.get(m[2].lower().replace("ç", "c"))
        if mes and (iso := _iso(int(m[3]), mes, int(m[1]))):
            return iso
    return None


def consolidado(texto: str) -> bool:
    return bool(_CONSOLIDADO.search(texto or ""))


def data_do_ato(
    titulo: str | None,
    texto: str | None,
    metadados: dict | None = None,
    natureza: str | None = None,
) -> str | None:
    """Data do ato em ISO, ou None. Metadados da fonte antes do título; consolidado nunca tem data.

    Metadados: publicação (data_publicacao_fonte, data_publicacao) antes da data do ato (data).
    Sem metadados: data no título e, nas consultas do DF, a linha "PUBLICADA NO DODF" do topo.
    """
    texto = texto or ""
    if natureza not in NATUREZAS_NAO_CONSOLIDAVEIS and consolidado(texto):
        return None
    for campo in ("data_publicacao_fonte", "data_publicacao", "data"):
        if iso := data_iso_br((metadados or {}).get(campo)):
            return iso
    if iso := data_do_titulo(titulo):
        return iso
    if m := _DODF.search(texto[:800]):
        return data_iso_br(m[1])
    return None
