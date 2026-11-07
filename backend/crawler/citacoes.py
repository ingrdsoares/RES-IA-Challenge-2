"""Extracao de citacoes normativas em texto livre."""

from dataclasses import dataclass

from backend.crawler.normas_id import _RX, NormaId, _sem_acento, norma_do_match

_ORGAOS_FEDERAIS = {"rfb", "srf", "cosit", "pgfn", "cgsn"}


@dataclass(frozen=True)
class Citacao:
    norma: NormaId
    trecho: str
    candidatas_jurisdicao: tuple[str, ...]


def extrair_citacoes(texto: str, jurisdicao_origem: str) -> list[Citacao]:
    """Uma Citacao por norma (primeira ocorrencia). Trecho vem do texto sem acento/minusculo."""
    t = _sem_acento(texto)
    vistas: set[str] = set()
    saida = []
    for m in _RX.finditer(t):
        jur = m.group("jur")
        if jur in ("df", "distrital", "gdf"):
            cands = ("df",)
        elif jur == "federal":
            cands = ("federal",)
        elif jurisdicao_origem == "df":
            cands = ("df", "federal")
        else:
            cands = ("federal",)
        # CGSN e orgaos da Receita/PGFN sao federais, mesmo citados em texto do DF
        if m.group("resol_cgsn") or _ORGAOS_FEDERAIS & set((m.group("orgao") or "").split("/")):
            cands = ("federal",)
        n = norma_do_match(m, cands[0])
        # sem ano e sem marcador (nº, n.), numero pequeno de tipo generico e ruido ("lei 12")
        generico = n.tipo in ("lei", "decreto") or (n.tipo == "portaria" and n.orgao is None)
        if n.ano is None and n.numero < 1000 and generico and not m.group("marc"):
            continue
        # sigla 'EC 08 de Taguatinga' em texto do DF e escola classe, nao emenda constitucional
        if n.tipo == "ec" and n.ano is None and jurisdicao_origem == "df" and m.group("ec") == "ec":
            continue
        if n.jurisdicao == "confaz":
            cands = ("confaz",)
        if n.chave in vistas:
            continue
        vistas.add(n.chave)
        saida.append(Citacao(n, t[max(0, m.start() - 40) : m.end() + 40].strip(), cands))
    return saida
