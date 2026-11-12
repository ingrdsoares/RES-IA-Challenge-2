"""Pergunta sobre o caso do usuário sem os dados necessários: pede os dados em vez de responder."""

import re

# Pergunta sobre a própria empresa ("minha empresa", "meu negócio", "minha ME").
_PROPRIA = re.compile(r"\b(minha|meu)\s+(empresa|neg[óo]cio|me|epp|mei|microempresa)\b", re.I)
_SIMPLES = re.compile(r"\bsimples\b", re.I)
_ELEGIBILIDADE = re.compile(r"\b(entrar|optar|enquadr\w*|pode|posso|consigo|participar)\b", re.I)
_ANEXO = re.compile(r"\b(qual|que)\s+anexo\b|\bfator\s+r\b", re.I)
_IMPOSTO = re.compile(r"\bquanto\s+(vou|devo|tenho\s+que)\s+pagar\s+de\s+(imposto|tributo)", re.I)
_ATRASO = re.compile(r"\b(atrasei|estou\s+atrasad[oa]|fiquei\s+atrasad[oa])\b", re.I)
_MULTA = re.compile(r"\bmultas?\b", re.I)
_JUROS = re.compile(r"\bjuros\b", re.I)
_ISS_EU_PAGO = re.compile(r"\bquanto\s+de\s+iss\s+(eu\s+)?(pago|devo)\b", re.I)
_RETER = re.compile(
    r"\b(preciso|devo|tenho\s+que)\s+reter\b.*\b(dess[ae]|dest[ae]|minha)\s+nota", re.I
)
_DIGITO = re.compile(r"\d")
# Pergunta sobre o próprio caso, em 1ª pessoa: só essas vão ao filtro com modelo (~1 s a mais).
_CASO_PROPRIO = re.compile(
    r"\b(minhas?|meus?|eu|sou|estou|tenho|posso|preciso|devo|vou|quero|abri|faturo|faturei"
    r"|atrasei|emiti|pago)\b",
    re.I,
)

# ponytail: regras por palavra-chave; qualquer dígito conta como "dado informado". Teto: não
# entende paráfrases nem valores por extenso ("duzentos mil"). Evoluir para classificador se
# o dataset de avaliação mostrar casos fora dessas sete famílias (multa/juros exigem verbo de atraso
# em 1ª pessoa; ISS e retenção exigem a frase "quanto de ISS eu pago" / "preciso reter ... dessa nota").
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
    "multa": ["qual declaração ou obrigação atrasou", "o regime tributário", "o período em atraso"],
    "juros": [
        "qual guia (tributo) está atrasada",
        "o valor original da guia",
        "o período em atraso",
    ],
    "iss": [
        "o município",
        "a atividade (serviço prestado)",
        "o regime tributário",
        "o valor do serviço",
    ],
    "retencao": [
        "o município do prestador e do tomador",
        "o serviço prestado",
        "quem é o tomador",
        "quem é o prestador",
    ],
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
    if _ATRASO.search(pergunta) and _JUROS.search(pergunta):
        return "juros"
    if _ATRASO.search(pergunta) and _MULTA.search(pergunta):
        return "multa"
    if _ISS_EU_PAGO.search(pergunta):
        return "iss"
    if _RETER.search(pergunta):
        return "retencao"
    return None


def caso_proprio(pergunta: str) -> bool:
    """Pergunta em 1ª pessoa, sobre o caso do usuário (candidata ao filtro com modelo)."""
    return bool(_CASO_PROPRIO.search(pergunta))


def texto_pedido(dados: list[str]) -> str:
    """Mensagem ao usuário pedindo os dados listados."""
    itens = "\n".join(f"- {item}" for item in dados)
    return (
        "Faltam dados para responder ao seu caso. Informe, por favor:\n"
        f"{itens}\n"
        "Com isso consigo consultar a base e orientar com segurança."
    )


def pedir_esclarecimento(pergunta: str) -> str | None:
    """Texto pedindo os dados que faltam, ou None se a pergunta pode seguir para a busca."""
    tipo = _tipo(pergunta)
    return texto_pedido(_PEDIDOS[tipo]) if tipo else None
