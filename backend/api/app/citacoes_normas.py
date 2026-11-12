"""Conferência de norma+artigo citados na resposta contra as fontes entregues.

Regra única, usada na API (CONFERIR_CITACOES) e na avaliação (citacao_suportada).
"""

import re

from app.normas import _ARTIGO, _forma_artigo, artigos_citados, chaves_normas, nome_norma
from app.sparse import fold

AVISO_NORMAS = (
    "\n\n(Atenção: as referências a seguir não constam das fontes consultadas "
    "e devem ser conferidas: {}.)"
)


def _campo(fonte, nome: str) -> str:
    valor = fonte.get(nome) if isinstance(fonte, dict) else getattr(fonte, nome, None)
    return valor or ""


def pares_fontes(sources) -> set[tuple[str, str]]:
    """Pares (norma, artigo) sustentados pelas fontes: citados no texto, ou artigo do texto + norma do título.

    O texto já inclui vizinhos quando a fonte foi expandida; artigo só no vizinho conta.
    """
    pares: set[tuple[str, str]] = set()
    for s in sources:
        texto = _campo(s, "text")
        pares.update(artigos_citados(texto))
        normas = chaves_normas(f"{_campo(s, 'title')} {_campo(s, 'source')}")
        artigos = {_forma_artigo(m) for m in re.finditer(_ARTIGO, fold(texto))}
        pares.update((n, a) for n in normas for a in artigos)
    return pares


def sem_suporte(answer: str, sources) -> list[tuple[str, str]]:
    """Pares (norma, artigo) da resposta que nenhuma fonte sustenta."""
    citados = artigos_citados(answer)
    if not citados:
        return []
    disponiveis = pares_fontes(sources)
    return [p for p in citados if p not in disponiveis]


def _rotulo(par: tuple[str, str]) -> str:
    norma, artigo = par
    numero, _, letra = artigo.partition("-")
    return f"art. {numero}{'-' + letra.upper() if letra else ''} da {nome_norma(norma)}"


def avisar_sem_suporte(answer: str, sources) -> tuple[str, list[tuple[str, str]]]:
    """Acrescenta aviso listando as referências sem fonte; o corpo da resposta não é alterado.

    Apagar o trecho no meio da frase poderia quebrar a resposta, e o parser não dá spans exatos.
    """
    faltam = sem_suporte(answer, sources)
    if not faltam:
        return answer, []
    return answer + AVISO_NORMAS.format("; ".join(_rotulo(p) for p in faltam)), faltam
