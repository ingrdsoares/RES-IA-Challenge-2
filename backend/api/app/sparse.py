"""Vetor esparso BM25 sem dependência: o IDF fica a cargo do Qdrant (Modifier.IDF)."""

import re
import unicodedata
import zlib
from collections import Counter

K1 = 1.2
B = 0.75
# ponytail: comprimento médio fixo, próximo ao de um chunk; calcular por coleção se o chunking mudar.
TOKENS_POR_CHUNK = 250
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[a-z]+")
_STOPWORDS = frozenset(
    "a o as os um uma uns umas de da do das dos em na no nas nos por pela pelo pelas pelos "
    "para com sem sob sobre e ou que se ao aos à às como qual quais quando onde foi ser são "
    "é há".split()
)


def fold(texto: str) -> str:
    """Minúsculas e sem acento: "Decreto Nº 43.982" vira "decreto no 43.982"."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def tokens(texto: str) -> list[str]:
    """Palavras e números; pontuação sai do número para "43.982" casar com "43982"."""
    saida = []
    for token in _TOKEN.findall(fold(texto)):
        if token[0].isdigit():
            saida.append(re.sub(r"[.,]", "", token))
        elif token not in _STOPWORDS and len(token) > 1:
            saida.append(token)
    return saida


def _indice(token: str) -> int:
    return zlib.crc32(token.encode())


def vetor_documento(texto: str) -> tuple[list[int], list[float]]:
    lista = tokens(texto)
    fator = K1 * (1 - B + B * len(lista) / TOKENS_POR_CHUNK)
    pesos: Counter[int] = Counter(_indice(t) for t in lista)
    indices = sorted(pesos)
    return indices, [pesos[i] * (K1 + 1) / (pesos[i] + fator) for i in indices]


PESO_EXPANSAO = 0.5


def vetor_consulta(texto: str) -> tuple[list[int], list[float]]:
    """Termos da pergunta pesam 1.0; sinônimos do glossário (só na consulta) pesam PESO_EXPANSAO."""
    from app.sinonimos import expandir_consulta  # import tardio: sinonimos importa fold daqui

    pesos = {_indice(t): PESO_EXPANSAO for t in tokens(expandir_consulta(texto))}
    pesos |= {_indice(t): 1.0 for t in tokens(texto)}
    indices = sorted(pesos)
    return indices, [pesos[i] for i in indices]
