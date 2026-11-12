"""Pergunta sobre o caso do usuário sem os dados necessários: pede os dados em vez de responder."""

import re

# Pergunta sobre a própria empresa ("minha empresa", "meu negócio", "minha ME").
_PROPRIA = re.compile(r"\b(minha|meu)\s+(empresa|neg[óo]cio|me|epp|mei|microempresa)\b", re.I)
_SIMPLES = re.compile(r"\bsimples\b", re.I)
_ELEGIBILIDADE = re.compile(r"\b(entrar|optar|enquadr\w*|pode|posso|consigo|participar)\b", re.I)
_ANEXO = re.compile(r"\b(qual|que)\s+anexo\b|\bfator\s+r\b", re.I)
_IMPOSTO = re.compile(r"\bquanto\s+(vou|devo|tenho\s+que)\s+pagar\s+de\s+(imposto|tributo)", re.I)
_DIGITO = re.compile(r"\d")

# ponytail: regras por palavra-chave; qualquer dígito conta como "dado informado". Teto: não
# entende paráfrases nem valores por extenso ("duzentos mil"). Evoluir para classificador se
# o dataset de avaliação mostrar casos fora dessas três famílias.
_PEDIDOS = {
    "simples": [
        "a atividade da empresa (CNAE)",
        "a receita bruta anual (faturamento)",
        "a situação da empresa (aberta ou em abertura, débitos, sócios)",
    ],
    "anexo": [
        "a atividade (CNAE) da empresa",
        "a receita bruta dos últimos 12 meses (RBT12)",
        "a folha de salários dos últimos 12 meses (inclui pró-labore e encargos)",
    ],
    "imposto": ["o regime tributário", "a atividade da empresa", "a receita do período"],
}


def _tipo(pergunta: str) -> str | None:
    if _DIGITO.search(pergunta):
        return None
    if _ANEXO.search(pergunta) and _PROPRIA.search(pergunta):
        return "anexo"
    if _SIMPLES.search(pergunta) and _PROPRIA.search(pergunta) and _ELEGIBILIDADE.search(pergunta):
        return "simples"
    if _IMPOSTO.search(pergunta):
        return "imposto"
    return None


def pedir_esclarecimento(pergunta: str) -> str | None:
    """Texto pedindo os dados que faltam, ou None se a pergunta pode seguir para a busca."""
    tipo = _tipo(pergunta)
    if tipo is None:
        return None
    itens = "\n".join(f"- {item}" for item in _PEDIDOS[tipo])
    return (
        "Faltam dados para responder ao seu caso. Informe, por favor:\n"
        f"{itens}\n"
        "Com isso consigo consultar a base e orientar com segurança."
    )
