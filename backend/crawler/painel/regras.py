"""Regras puras do painel: o que pular, como classificar o resultado, barra de progresso e tempo estimado."""

from .frentes import FRENTES

_TETO = 0.99  # a linha só chega a 100% ao terminar


def deve_pular(resumo: dict | None, ultima: dict | None, refazer: bool) -> bool:
    if refazer or not resumo or not resumo.get("itens"):
        return False
    return (ultima or {}).get("resultado") not in ("erro", "interrompida")


def planejar(
    selecionadas: set[str], refazer: set[str], resumos: dict, ultimas: dict, *, frentes=FRENTES
) -> list[dict]:
    necessarias: dict[str, str] = {}  # dependência sem dados -> quem a exige
    itens = []
    for f in reversed(
        frentes
    ):  # dependências vêm antes na ordem, então o fecho transitivo sai numa só passada
        resumo = resumos.get(f.pasta)
        if f.modulo in selecionadas:
            pular = deve_pular(resumo, ultimas.get(f.modulo), f.modulo in refazer)
            item = {
                "modulo": f.modulo,
                "acao": "pular" if pular else "rodar",
                "motivo": "já tem dados" if pular else "selecionada",
            }
        elif f.modulo in necessarias:
            if (resumo or {}).get("itens"):
                continue  # dependência com dados não precisa rodar
            item = {
                "modulo": f.modulo,
                "acao": "rodar",
                "motivo": f"necessária para {necessarias[f.modulo]}",
            }
        else:
            continue
        if item["acao"] == "rodar":
            for d in f.depende:
                if d not in selecionadas:
                    necessarias.setdefault(d, f.modulo)
        itens.append(item)
    return itens[::-1]


def classificar(saida: int | None, excecao: bool, interrompida: bool, situacao: str | None) -> str:
    if interrompida:
        return "interrompida"
    if excecao:
        return "erro"
    if saida in (0, 1) and situacao == "coletada_com_pendencias":
        return "parcial"
    return "concluida" if saida == 0 else "erro"


def barra(
    requisicoes: int, urls_casadas: int, ultimas_requisicoes: int | None, origens: int
) -> tuple[float | None, int | None]:
    if ultimas_requisicoes and ultimas_requisicoes > 0:
        return min(requisicoes / ultimas_requisicoes, _TETO), 1
    if origens > 0 and urls_casadas > 0:
        return min(urls_casadas / origens, _TETO), 2
    return None, None


def estimar(
    duracao_anterior: float | None,
    decorrido: float | None,
    fracao: float | None,
    s_por_item: float | None,
    itens: int,
) -> float | None:
    if decorrido and fracao and fracao > 0:
        return decorrido * (1 - fracao) / fracao
    if duracao_anterior is not None:
        return max(duracao_anterior - (decorrido or 0), 0)
    if s_por_item and itens:
        return s_por_item * itens
    return None
