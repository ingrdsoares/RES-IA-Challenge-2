"""Divide perguntas compostas em partes, por regra, para buscar trechos de cada uma."""

import re

from app.sparse import fold

_INTERROGATIVAS = (
    "qual",
    "quais",
    "quem",
    "quando",
    "ate quando",
    "ate que",
    "como",
    "onde",
    "quanto",
    "quantos",
    "quantas",
    "em quanto",
    "em quantos",
    "o que",
    "por que",
)
# ponytail: segunda oração sem interrogativa ("e ele pode emitir?") só é reconhecida por pronome
# opcional + verbo modal desta lista; verbo fora dela não divide. Subir para análise sintática se preciso.
_MODAIS = (
    r"(?:(?:ele|ela|eles|elas|voce|ja)\s+)?(?:tambem\s+)?"
    r"(?:pode|podem|posso|precisa|precisam|preciso|deve|devem|devo|tem\s+que|tem\s+de|tenho\s+que"
    r"|e\s+obrigad[oa]s?|sao\s+obrigad[oa]s?)"
)
_EMENDA = re.compile(
    r",?\s+e\s+(?=(?:"
    + "|".join(i.replace(" ", r"\s+") for i in _INTERROGATIVAS)
    + r"|"
    + _MODAIS
    + r")\s)"
)
_PREFIXO = re.compile(r"\A\s*((?:qual|quais|quem|quando)\s+(?:e|sao|foi)\s+|o que\s+)")
# Siglas (ISS, NFS-e, DASN-Simei) e normas citadas (LC 87, Lei 9.430), que dão o assunto à parte.
_CONTEXTO = re.compile(
    r"\b(?:[A-Z]{2,}(?:-[A-Za-z]+)?|(?:LC|Lei|Decreto|Resolução)(?: DF| CGSN)? n?º? ?[\d.]+)\b"
)
MAX_PARTES = 3
# ponytail: parte com menos palavras que isto herda o assunto da primeira ("e qual é a máxima?").
CURTA = 7


def partes_da_pergunta(pergunta: str) -> list[str]:
    """Partes da pergunta; uma só quando não há divisão segura."""
    texto = " ".join(pergunta.split())
    tema, corpo = "", texto
    if ":" in texto[:40]:
        tema, corpo = (s.strip() for s in texto.split(":", 1))
    frases = [f.strip() for f in re.split(r"(?<=\?)\s+", corpo) if f.strip()]
    if len(frases) < 2:
        dobrado = fold(corpo)
        cortes = [m.start() for m in _EMENDA.finditer(dobrado)]
        limites = [0, *[m.end() for m in _EMENDA.finditer(dobrado)]]
        frases = [
            corpo[ini:fim].strip(" ,?")
            for ini, fim in zip(limites, [*cortes, len(corpo)], strict=True)
        ]
    frases = [f.strip(" ,?") for f in frases if len(f.split()) >= 2]
    if len(frases) < 2:
        return [texto]
    return [f"{tema}: {f}" if tema else f for f in frases[:MAX_PARTES]]


def consultas_de_busca(partes: list[str]) -> list[str]:
    """Texto de busca de cada parte.

    Parte sem sigla ou norma própria herda as das partes anteriores ("e qual é a sua base de
    cálculo?" leva ISS). Parte curta recebe também o assunto da primeira ("e qual é a máxima?").
    """
    if len(partes) < 2:
        return partes
    assunto = _PREFIXO.sub("", fold(partes[0]))
    consultas = [partes[0]]
    for i, parte in enumerate(partes[1:], 1):
        if not re.search(_CONTEXTO, parte):
            herdado = re.findall(_CONTEXTO, " ".join(partes[:i]))
            parte = " ".join([parte, *dict.fromkeys(herdado)])
        if len(partes[i].split()) < CURTA:
            parte = f"{parte} {assunto}"
        consultas.append(parte)
    return consultas
