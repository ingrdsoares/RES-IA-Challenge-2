"""Limpeza do Markdown do recorte antes do chunking.

O recorte já chega em Markdown (o ``limpeza_html`` é para o HTML bruto da coleta). Aqui só
sai o ruído que dilui o embedding: URL de link, URL solta, imagem, rodapé de página e de
assinatura, linha de tabela vazia, negrito ``**`` (esconde ``Art.`` do chunker), nbsp e
espaço repetido, e linha curta repetida no mesmo documento (cabeçalho/rodapé de página).

Não toca em ``~~riscado~~`` nem em linhas que começam com ``>`` ou ``#``: o bridge usa
"> Marcadores da fonte" para tirar o texto tachado e o chunker usa os títulos.
"""

from __future__ import annotations

import re
from collections import Counter

_IMAGEM = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)")
# [texto](url) -> texto; aceita um nível de parênteses dentro da URL.
_LINK = re.compile(r"\[([^\]\n]*)\]\((?:[^()\s]|\([^()\s]*\))*\)")
_URL = re.compile(r"(?<![\w(/])(?:https?://|www\.)[^\s)>\]|]*[^\s)>\]|.,;:]")
_RODAPE = re.compile(
    r"^(?:p[áa]gina\s*\d+(?:\s*(?:de|/)\s*\d+)?"
    r"|documento validado"
    r"|assinad[oa] digitalmente\b.*"
    r"|assinatura digital"
    r"|processo clique aqui para inserir o texto"
    r"|\(\.\.\.\)|\[\.\.\.\]|\.\.\."
    r"|> fotografia das vis[õo]es da fonte\b.*)$",
    re.IGNORECASE,
)
_TABELA_VAZIA = re.compile(r"^\|(?:[\s:|-]*\|)?\s*$")
_ESTRUTURA = re.compile(
    r"^(?:[#>|]|~~|art\.|§|par[áa]grafo|cap[íi]tulo|se[çc][ãa]o|t[íi]tulo|subse[çc][ãa]o|livro)",
    re.IGNORECASE,
)
REPETICOES_MIN = 5


def _repetidas(linhas: list[str]) -> set[str]:
    """Linhas curtas, de 3+ palavras, que se repetem no documento: cabeçalho/rodapé de página."""
    contagem = Counter(
        s
        for s in (linha.strip() for linha in linhas)
        if 10 <= len(s) <= 200 and len(s.split()) >= 3 and not _ESTRUTURA.match(s)
    )
    return {s for s, n in contagem.items() if n >= REPETICOES_MIN}


def limpar_markdown(texto: str) -> str:
    texto = texto.replace(" ", " ").replace("**", "")
    texto = _IMAGEM.sub("", texto)
    texto = _LINK.sub(r"\1", texto)
    texto = _URL.sub("", texto)
    linhas = texto.split("\n")
    repetidas = _repetidas(linhas)
    saida = []
    for linha in linhas:
        s = linha.strip()
        if s in repetidas or _RODAPE.match(s) or (s.startswith("|") and _TABELA_VAZIA.match(s)):
            continue
        saida.append(re.sub(r"[ \t]{2,}", " ", linha.rstrip()))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(saida)).strip()
