"""Chaves de norma ("lc:87", "decreto:43982") a partir do título do documento ou da pergunta."""

import re

from app.sparse import fold

_NUMERO = r"(?:n[o.]?\s*\.?\s*)?(\d{1,3}(?:\.\d{3})+|\d+)"
_PADROES = (
    ("lc", rf"\b(?:lei complementar|lc)\s*(?:federal\s*)?{_NUMERO}"),
    ("dl", rf"\b(?:decreto[- ]lei|dl)\s*{_NUMERO}"),
    ("lei", rf"(?<!decreto-)(?<!decreto )\blei\s*(?:federal\s*|distrital\s*)?{_NUMERO}"),
    ("decreto", rf"\bdecreto\s*(?:federal\s*|distrital\s*|df\s*)?{_NUMERO}"),
    ("ec", rf"\b(?:emenda constitucional|ec)\s*{_NUMERO}"),
    ("in", rf"\b(?:instrucao normativa|in)\s*(?:rfb\s*|srf\s*)?{_NUMERO}"),
    ("resolucao", rf"\b(?:resolucao|resol\.)\s*(?:cgsn\s*)?{_NUMERO}"),
    ("portaria", rf"\b(?:portaria|port\.)\s*(?:pgfn\s*|rfb\s*)?{_NUMERO}"),
)
_APELIDOS = (
    (r"\blei kandir\b", "lc:87"),
    (r"\bctn\b|\bcodigo tributario nacional\b", "lei:5172"),
)
_NOMES = {
    "lc": "Lei Complementar",
    "dl": "Decreto-Lei",
    "lei": "Lei",
    "decreto": "Decreto",
    "ec": "Emenda Constitucional",
    "in": "Instrução Normativa",
    "resolucao": "Resolução",
    "portaria": "Portaria",
}


def chaves_normas(texto: str | None) -> list[str]:
    """Chaves citadas, na ordem de tipo, sem repetir. O mesmo código para título e pergunta."""
    dobrado = fold(texto or "")
    chaves: list[str] = []
    for tipo, padrao in _PADROES:
        for numero in re.findall(padrao, dobrado):
            chaves.append(f"{tipo}:{numero.replace('.', '')}")
    chaves += [chave for padrao, chave in _APELIDOS if re.search(padrao, dobrado)]
    return list(dict.fromkeys(chaves))


def nome_norma(chave: str) -> str:
    tipo, numero = chave.split(":")
    return f"{_NOMES[tipo]} {numero}"
