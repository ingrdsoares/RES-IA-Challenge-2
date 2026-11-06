"""Lista fixa das frentes de coleta (ordem de execução) e leitura do catálogo consolidado."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from ..catalogo import FRONTES

ETAPAS_FINAIS = ("estatisticas", "sumarizacao")
MODULO_CATALOGO = "catalogo"
_NOME_POR_PASTA = {pasta: nome for nome, pasta in FRONTES.items()}
_PASTA_EXCECAO = {"anexos": "anexos-cgsn140", "recuperar_anexos": "anexos-recuperados"}
_LOCAL = "usa cópia local"


@dataclass(frozen=True)
class Frente:
    modulo: str
    pasta: str
    depende: tuple[str, ...] = ()
    pesada: str | None = None
    marcas: tuple[str, ...] = ()

    @property
    def nome(self) -> str:
        return _NOME_POR_PASTA.get(self.pasta, self.pasta)


def _f(modulo, depende=(), pesada=None, marcas=()):
    return Frente(
        modulo,
        _PASTA_EXCECAO.get(modulo, modulo.replace("_", "-")),
        tuple(depende),
        pesada,
        tuple(marcas),
    )


_ZIPS_CNPJ = "Baixa zips da Receita (cada um com até 700 MB) para a pasta de dados; "
FRENTES: tuple[Frente, ...] = (
    _f("cnae"),
    _f("notas_cnae"),
    _f("legislacao"),
    _f("legislacao_complementar"),
    _f("anexos", ["legislacao"]),
    _f("manuais"),
    _f("mei"),
    _f("complemento_contabil"),
    _f("contabilidade"),
    _f("obrigacoes", marcas=["período fixo: 2026-11"]),
    _f("obrigacoes_avancadas"),
    _f("calendario_df", ["obrigacoes"]),
    _f("documentos_fiscais"),
    _f("notas_tecnicas_fiscais"),
    _f("xmls_exemplo", marcas=[_LOCAL]),
    _f("tabelas_fiscais"),
    _f("sped_complementar", marcas=[_LOCAL]),
    _f("tributacao_lucro"),
    _f("regularizacao_fiscal"),
    _f("distrital_df"),
    _f("icms_consultas_df"),
    _f(
        "consultas_df_amplas",
        pesada="Consulta anos de 2010 a 2026 na API da Receita e várias páginas do TARF; "
        "são milhares de documentos, com até 3 requisições simultâneas por servidor.",
    ),
    _f(
        "consultas_rfb",
        marcas=[_LOCAL],
        pesada="Reaproveita a cópia local já baixada, mas ler e revalidar milhares de atos pode levar bastante tempo.",
    ),
    _f("sumulas_classificacao", marcas=[_LOCAL]),
    _f("documentos_jurisprudencia"),
    _f("fontes_recuperadas", ["documentos_jurisprudencia"]),
    _f("reforma"),
    _f("reforma_historico", marcas=[_LOCAL]),
    _f(
        "retencoes_defesa_setores",
        marcas=[_LOCAL],
        pesada="Reaproveita a cópia local já baixada, mas ler e revalidar até 2.000 atos pode levar bastante tempo.",
    ),
    _f("recuperar_anexos", ["reforma_historico", "retencoes_defesa_setores"]),
    _f(
        "historico_competencias",
        marcas=[_LOCAL],
        pesada="Percorre as páginas de 2018 a 2025 e consulta a listagem de competências do CNPJ; "
        "são centenas de requisições, com até 3 em paralelo.",
    ),
    _f("economia", marcas=["período fixo: até 2026-11-03"]),
    _f("ibge_indicadores"),
    _f("sebrae"),
    _f("indicadores_empresariais"),
    _f("cnpj"),
    _f(
        "cnpj_ampliado",
        marcas=["período fixo: 2026-10", "reescreve metadados da coleta existente"],
        pesada=_ZIPS_CNPJ
        + "baixa 3 arquivos (Estabelecimentos1, Empresas2 e Simples) e lê todos para montar a amostra.",
    ),
    _f(
        "cnpj_df",
        ["cnpj_ampliado"],
        marcas=["período fixo: 2026-10"],
        pesada=_ZIPS_CNPJ + "usa 4 arquivos (Estabelecimentos1, Empresas1, Empresas2 e Simples), "
        "reaproveitando os já baixados por cnpj_ampliado.",
    ),
    _f(
        "cnpj_df_censo",
        ["cnpj_ampliado"],
        marcas=["período fixo: 2026-10"],
        pesada="Baixa e lê 21 zips da Receita (10 de estabelecimentos, 10 de empresas e o Simples), "
        "cada um com até 3 GB: dezenas de GB e várias horas.",
    ),
    _f(
        "casos_oficiais",
        [
            "complemento_contabil",
            "distrital_df",
            "manuais",
            "mei",
            "notas_tecnicas_fiscais",
            "obrigacoes_avancadas",
            "sped_complementar",
        ],
    ),
)
POR_MODULO: dict[str, Frente] = {f.modulo: f for f in FRENTES}


def carregar_catalogo(data: Path) -> dict | None:
    try:
        catalogo = json.loads(
            (Path(data) / "catalogo" / "catalogo.json").read_text(encoding="utf-8")
        )
        return catalogo if isinstance(catalogo, dict) else None
    except (OSError, ValueError):
        return None


def resumir_catalogo(catalogo: dict | None) -> dict[str, dict]:
    if not catalogo or not isinstance(catalogo, dict):
        return {}
    por_pasta: dict[str, dict] = {}
    for s in catalogo.get("snapshots") or []:
        r = por_pasta.setdefault(
            s["diretorio"].split("/")[0], {"itens": 0, "ultima_coleta": None, "origens": set()}
        )
        r["itens"] += 1
        if s.get("coletado_em") and (
            r["ultima_coleta"] is None or s["coletado_em"] > r["ultima_coleta"]
        ):
            r["ultima_coleta"] = s["coletado_em"]
        if s.get("origem"):
            r["origens"].add(s["origem"])
    for c in catalogo.get("cobertura_frentes") or []:
        r = por_pasta.setdefault(c["pasta"], {"itens": 0, "ultima_coleta": None, "origens": set()})
        r["itens"] = r["itens"] if c.get("snapshots") is None else c["snapshots"]
        r["situacao"] = c.get("situacao")
        r["pendencias"] = (c.get("erros_manifesto_mais_recente") or 0) + (
            c.get("pendencias_extracao") or 0
        )
    for r in por_pasta.values():
        dominios = Counter(urlsplit(o).hostname for o in r["origens"])
        r["fonte"] = dominios.most_common(1)[0][0] if dominios else None
        r.setdefault("situacao", None)
        r.setdefault("pendencias", 0)
    return por_pasta
