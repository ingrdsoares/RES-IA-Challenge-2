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
_ARTIGO = r"\bart(?:igo)?s?\.?\s*(\d+)\s*o?(?:\s*-\s*([a-z])\b)?"
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


def _forma_artigo(achado: re.Match) -> str:
    numero, letra = achado.groups()
    return f"{numero}-{letra}" if letra else numero


def _posicoes_normas(dobrado: str) -> list[tuple[int, str]]:
    achadas = []
    for tipo, padrao in _PADROES:
        for m in re.finditer(padrao, dobrado):
            achadas.append((m.start(), f"{tipo}:{m.group(1).replace('.', '')}"))
    for padrao, chave in _APELIDOS:
        achadas += [(m.start(), chave) for m in re.finditer(padrao, dobrado)]
    return achadas


def chaves_normas(texto: str | None) -> list[str]:
    """Chaves citadas, na ordem de tipo, sem repetir. O mesmo código para título e pergunta."""
    dobrado = fold(texto or "")
    chaves: list[str] = []
    for tipo, padrao in _PADROES:
        for numero in re.findall(padrao, dobrado):
            chaves.append(f"{tipo}:{numero.replace('.', '')}")
    chaves += [chave for padrao, chave in _APELIDOS if re.search(padrao, dobrado)]
    return list(dict.fromkeys(chaves))


def chave_artigo(rotulo: str | None) -> str | None:
    """Forma comparável do artigo: "Art. 8º-A" vira "8-a"; rótulo sem artigo vira None."""
    achado = re.search(_ARTIGO, fold(rotulo or ""))
    return _forma_artigo(achado) if achado else None


def artigos_citados(pergunta: str) -> list[tuple[str, str]]:
    """Pares (norma, artigo) citados. Cada artigo fica com a primeira norma depois dele."""
    # ponytail: em "arts. 3º e 5º" só o primeiro conta; ampliar se esse formato aparecer.
    dobrado = fold(pergunta)
    normas = sorted(_posicoes_normas(dobrado))
    pares: list[tuple[str, str]] = []
    for achado in re.finditer(_ARTIGO, dobrado):
        seguintes = [chave for pos, chave in normas if pos >= achado.end()]
        anteriores = [chave for pos, chave in normas if pos < achado.start()]
        norma = seguintes[0] if seguintes else anteriores[-1] if anteriores else None
        if norma:
            pares.append((norma, _forma_artigo(achado)))
    return list(dict.fromkeys(pares))


def nome_norma(chave: str) -> str:
    tipo, numero = chave.split(":")
    return f"{_NOMES[tipo]} {numero}"
