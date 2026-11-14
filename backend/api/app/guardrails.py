"""Guardrails sobre o texto da resposta: recusa e pedido de dados viram status explícitos."""

import re

_RECUSA = re.compile(
    r"^(os|as) (documentos|trechos|fontes|informações)[^.]{0,80}"
    r"(não (tratam|trata|contêm|contém|fornecem|abordam|mencionam)|não há)",
    re.IGNORECASE,
)
_DADOS = re.compile(
    r"(que você não informou|você não informou|forneça (esses|os) dados|informe,? por favor)",
    re.IGNORECASE,
)
_LIMITE_RECUSA = 450  # recusa é curta; resposta longa que começa assim ainda traz conteúdo


def e_recusa(resposta: str) -> bool:
    """Resposta que declara que a base não cobre o assunto."""
    texto = resposta.strip()
    return bool(_RECUSA.search(texto)) and len(texto) <= _LIMITE_RECUSA


def pede_dados(resposta: str) -> bool:
    """Resposta que pede ao usuário os dados que faltam em vez de responder."""
    return bool(_DADOS.search(resposta))
