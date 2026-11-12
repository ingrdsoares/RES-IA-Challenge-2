"""Glossário curado de siglas e termos coloquiais -> grafia do texto legal (só no lado da consulta)."""

import re

from app.sparse import fold

# Siglas de tributos que o próprio texto legal usa (ISS, ICMS, IRPJ...) ficam de fora: expandir só adiciona ruído.
# Siglas: casam só em MAIÚSCULAS no texto original ("IR" não pega o verbo "ir", "ME" não pega "me").
_SIGLAS = {
    "DAS": "documento de arrecadação do simples nacional",
    "DASN": "declaração anual do simples nacional simei",
    "RBT12": "receita bruta acumulada nos doze meses anteriores",
    "RBA": "receita bruta acumulada",
    "MEI": "microempreendedor individual",
    "PJ": "pessoa jurídica",
    "PF": "pessoa física",
    "IR": "imposto sobre a renda",
    "INSS": "contribuição previdenciária",
    "ME": "microempresa",
    "EPP": "empresa de pequeno porte",
    "CNAE": "classificação nacional de atividades econômicas",
    "NF": "nota fiscal",
    "NFE": "nota fiscal eletrônica",
    "NFSE": "nota fiscal de serviços eletrônica",
    "NF-E": "nota fiscal eletrônica",
    "NFS-E": "nota fiscal de serviços eletrônica",
    "ISSQN": "iss",
    "ST": "substituição tributária",
}

# Termos livres: casam em texto dobrado (sem acento/caixa), com fronteira de palavra.
_TERMOS = {
    "faturamento": "receita bruta",
    "pejotizacao": "pessoa jurídica prestação de serviços pessoais empregado",
    "nota fiscal": "nf-e nfs-e documento fiscal eletrônico",
    "nota fiscal eletronica": "nf-e nfs-e",
    "fator r": "relação folha de salários receita bruta anexo iii anexo v",
    "dasn-simei": "declaração anual simplificada microempreendedor individual",
    "documento de arrecadacao do simples nacional": "das",
    "receita bruta acumulada nos doze meses anteriores": "rbt12",
    "microempreendedor individual": "mei",
    "microempresa": "me",
    "empresa de pequeno porte": "epp",
    "imposto sobre a renda": "ir",
    "imposto de renda": "imposto sobre a renda ir",
    "previdencia": "contribuição previdenciária inss",
    "desenquadramento": "exclusão simples nacional",
}

_RE_SIGLAS = re.compile(
    r"(?<![\w-])("
    + "|".join(sorted(map(re.escape, _SIGLAS), key=len, reverse=True))
    + r")(?![\w-])"
)
_RE_TERMOS = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _TERMOS), key=len, reverse=True)) + r")\b"
)
_FOLDED = {fold(k): v for k, v in _TERMOS.items()}


def expandir_consulta(texto: str) -> str:
    """Só as expansões (vazio se nada casa); quem consome decide o peso."""
    # ponytail: lista fixa, sem desambiguar contexto ("ST", "NF" em maiúsculas sempre expandem);
    # se precisar de mais cobertura, mover o glossário para dados e medir recall no ground truth.
    achados = [_SIGLAS[m] for m in _RE_SIGLAS.findall(texto)]
    achados += [_FOLDED[m] for m in _RE_TERMOS.findall(fold(texto))]
    return " ".join(dict.fromkeys(achados))
