"""Roteiro de medição da rodada 2: um comando roda todos os experimentos e compara com a linha de base.

Para cada experimento (data/benchmark/experimentos.exemplo.json):
  1. monta o ambiente (padrões da linha de base + env do experimento) e CONFERE os valores efetivos
     (Settings() lido num subprocesso com esse ambiente). Divergência aborta o experimento: o
     `.env` ignorado em silêncio já falseou uma rodada;
  2. `python -m evaluation run` (em backend/api) no conjunto ampliado, com --repeticoes N;
  3. confere de novo, agora no manifest.json que a própria execução gravou;
  4. scripts/medir_recuperacao_qdrant.py (Recall@8 e MRR, estritos e lenientes);
  5. grava resultado.json. Experimento com resultado.json é pulado (retomável).
No fim, uma tabela única (comparacao.md e comparacao.json) contra a linha de base, em dois recortes:
todos os casos e sem os casos com metadata.fonte_so_no_recorte_completo.

Como o RAG é alcançado: a avaliação (evaluation.adapter.InternalRagClient) e a medição de recuperação
rodam a API em processo, com Settings() lido do ambiente. Basta passar o env ao subprocesso: não há
Docker nem HTTP, então não há contêiner para reiniciar. Os serviços (Qdrant, Ollama, reranker) precisam
estar no ar; o script não os sobe.

Uso (na raiz do repositório, com o Python do ambiente da API/avaliação):
  python scripts/experimentos.py --config data/benchmark/experimentos.exemplo.json --dry-run
  python scripts/experimentos.py --config data/benchmark/experimentos.exemplo.json
  python scripts/experimentos.py --config ... --so base_v2,candidate_k_60 --repeticoes 1
"""

import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
API = RAIZ / "backend" / "api"
sys.path.insert(0, str(API))

PADRAO_CONJUNTO = "backend/evaluation/data/teste_ampliado_2026-11-12.jsonl"
RECORTE = ("todos", "sem_recorte_completo")

# Metas da seção 3.1 de metricas-avaliacao-rag.md: chave -> (operador, limite, rótulo).
METAS = {
    "respostas_erradas": ("<=", 0, "0"),
    "recusa_indevida": ("<=", 0.05, "≤5%"),
    "recusa_fora_acervo": (">=", 1.0, "100%"),
    "clarify": (">=", 0.8, "≥80%"),
    "falso_positivo": ("<=", 0, "0"),
    "citacao_suportada": (">=", 0.95, "≥0,95"),
    "artigo_esperado": (">=", 0.80, "≥0,80"),
    "recall8_leniente": (">=", 0.80, "≥0,80"),
    "mrr8_leniente": (">=", 0.65, "≥0,65"),
    "lat_mediana": ("<=", 5.0, "≤5 s"),
    "lat_p95": ("<=", 15.0, "≤15 s"),
    "conc_fontes": (">=", 1.0, "100%"),
    "conc_resposta": (">=", 0.90, "≥90%"),
}
# Sem meta absoluta: "não piorar" em relação à linha de base.
NAO_PIORAR = ("rouge_l", "bert_score")

# (chave, rótulo). Contagens aparecem como "a/b" no texto, o valor da tabela é a taxa.
COLUNAS = [
    ("respostas_boas", "Respostas boas"),
    ("respostas_erradas", "Erradas"),
    ("recusa_indevida", "Recusa indevida"),
    ("recusa_fora_acervo", "Recusa fora do acervo"),
    ("rouge_l", "ROUGE-L"),
    ("bert_score", "BERTScore"),
    ("artigo_esperado", "artigo_esperado"),
    ("citacao_suportada", "citacao_suportada"),
    ("clarify", "Clarify (acerto)"),
    ("falso_positivo", "Falso positivo"),
    ("recall8", "Recall@8 estrito"),
    ("mrr8", "MRR estrito"),
    ("recall8_leniente", "Recall@8 leniente"),
    ("mrr8_leniente", "MRR leniente"),
    ("lat_mediana", "Latência mediana (s)"),
    ("lat_p95", "Latência p95 (s)"),
    ("conc_resposta", "Concordância resposta"),
    ("conc_fontes", "Concordância fontes"),
]

# Padrões da linha de base (seção "Roteiro de medição", passo 1); todo experimento parte daqui.
PARAMETROS_PADRAO = {
    "CANDIDATE_K": "30",
    "LEGISLATION_BOOST": "0.2",
    "RERANK_LEGISLATION_BOOST": "0",
    "CONTEXT_WINDOW_CHARS": "0",
    "MAX_TRECHOS_POR_DOCUMENTO": "0",
    "ESCLARECIMENTO_MODELO": "false",
    "CONFERIR_CITACOES": "false",
    "PESO_EXPANSAO": "0.5",
}


class ConfigInvalida(ValueError):
    pass


class ExperimentoAbortado(RuntimeError):
    pass


# ---------------------------------------------------------------- configuração


def _texto_env(valor) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float, str)):
        return str(valor)
    raise ConfigInvalida(f"valor de env inválido: {valor!r}")


def carregar_config(caminho: Path) -> dict:
    """Lê e valida o JSON; devolve a config com `experimentos[i]["env_final"]` já montado."""
    cfg = json.loads(Path(caminho).read_text(encoding="utf-8"))
    experimentos = cfg.get("experimentos")
    if not isinstance(experimentos, list) or not experimentos:
        raise ConfigInvalida("'experimentos' deve ser uma lista não vazia")
    reps = cfg.setdefault("repeticoes", 3)
    if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
        raise ConfigInvalida("'repeticoes' deve ser inteiro >= 1")
    cfg.setdefault("conjunto", PADRAO_CONJUNTO)
    cfg.setdefault("split", "final")
    if cfg["split"] not in ("development", "final"):
        raise ConfigInvalida("'split' deve ser development ou final")
    comum = cfg.setdefault("env_comum", {})
    nomes = set()
    for exp in experimentos:
        nome = exp.get("nome", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", nome):
            raise ConfigInvalida(f"nome de experimento inválido: {nome!r}")
        if nome in nomes:
            raise ConfigInvalida(f"nome de experimento repetido: {nome}")
        nomes.add(nome)
        env = {**PARAMETROS_PADRAO, **comum, **exp.get("env", {})}
        for chave in env:
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", chave):
                raise ConfigInvalida(f"{nome}: nome de variável inválido: {chave!r}")
        exp["env_final"] = {k: _texto_env(v) for k, v in env.items()}
        if not exp["env_final"].get("COLLECTION_NAME"):
            raise ConfigInvalida(f"{nome}: COLLECTION_NAME é obrigatório")
    if cfg.get("baseline") not in nomes:
        raise ConfigInvalida("'baseline' deve ser o nome de um dos experimentos")
    return cfg


# ---------------------------------------------------------------- verificação do ambiente


def _igual(esperado: str, efetivo) -> bool:
    esperado = esperado.strip()
    if efetivo is None:
        return esperado == ""
    if isinstance(efetivo, bool):
        return esperado.lower() in (
            {"true", "1", "yes", "on"} if efetivo else {"false", "0", "no", "off", ""}
        )
    if isinstance(efetivo, (int, float)):
        try:
            return float(esperado) == float(efetivo)
        except ValueError:
            return False
    return str(efetivo).rstrip("/") == esperado.rstrip("/")


def divergencias(env: dict, settings: dict) -> list[str]:
    """Variáveis cujo valor efetivo em Settings difere do pedido (ou que Settings desconhece)."""
    erros = []
    for chave, esperado in env.items():
        campo = chave.lower()
        if campo not in settings:
            erros.append(f"{chave}: Settings não tem o campo '{campo}' (variável ignorada)")
        elif not _igual(esperado, settings[campo]):
            erros.append(f"{chave}: pedido {esperado!r}, efetivo {settings[campo]!r}")
    return erros


def settings_efetivas(python: str, env: dict) -> dict:
    """Settings() construída num subprocesso com o ambiente do experimento, como a avaliação fará."""
    codigo = "from app.config import Settings; print(Settings().model_dump_json())"
    r = subprocess.run(
        [python, "-c", codigo],
        cwd=API,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise ExperimentoAbortado(f"não foi possível ler Settings: {r.stderr.strip()[-300:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def conferir(env: dict, settings: dict, onde: str) -> None:
    erros = divergencias(env, settings)
    if erros:
        raise ExperimentoAbortado(f"configuração efetiva diverge ({onde}): " + "; ".join(erros))


# ---------------------------------------------------------------- métricas da avaliação


def _fidelidade(linha: dict) -> dict:
    """artigo_esperado e citacao_suportada (f1 ou None) de uma tentativa de results.json."""
    from evaluation.metrics.fidelidade import artigo_esperado, citacao_suportada
    from evaluation.schemas import AttemptResult, EvalCase

    caso = EvalCase.model_validate(linha["case"])
    tentativa = AttemptResult.model_validate(linha["attempt"])
    saida = {}
    for nome, fn in (
        ("artigo_esperado", artigo_esperado),
        ("citacao_suportada", citacao_suportada),
    ):
        s = fn(caso, tentativa)
        saida[nome] = s.f1 if s.state == "success" else None
    return saida


def _media_por_pergunta(linhas, valor) -> float | None:
    """Média das repetições de cada pergunta, depois média das perguntas (como o relatório)."""
    por_id = defaultdict(list)
    for linha in linhas:
        v = valor(linha)
        if v is not None:
            por_id[linha["case"]["id"]].append(v)
    medias = [sum(v) / len(v) for v in por_id.values()]
    return sum(medias) / len(medias) if medias else None


def _taxa(linhas, comportamento, status) -> dict:
    alvo = [r for r in linhas if r["case"].get("expected_behavior", "answer") == comportamento]
    alvo = [r for r in alvo if r["attempt"]["state"] == "success"]
    n = sum(r["attempt"].get("rag_status") in status for r in alvo)
    return {"n": n, "total": len(alvo), "taxa": n / len(alvo) if alvo else None}


def _concordancia(linhas) -> tuple[float | None, float | None]:
    por_id = defaultdict(list)
    for r in linhas:
        if r["attempt"]["state"] == "success":
            por_id[r["case"]["id"]].append(r["attempt"])

    def parte(valores):
        return max(valores.count(v) for v in valores) / len(valores)

    resp, fontes = [], []
    for tentativas in por_id.values():
        if len(tentativas) < 2:
            continue
        resp.append(parte([" ".join((a.get("answer") or "").split()) for a in tentativas]))
        fontes.append(
            parte(
                [
                    tuple(str(s.get("chunk_id") or s.get("id")) for s in a["sources"])
                    for a in tentativas
                ]
            )
        )
    media = lambda v: sum(v) / len(v) if v else None  # noqa: E731
    return media(resp), media(fontes)


def metricas_avaliacao(linhas: list[dict], sem_recorte_completo: bool, fidelidade=None) -> dict:
    """Métricas de uma execução (linhas = results.json) em um dos dois recortes."""
    fidelidade = fidelidade or _fidelidade
    if sem_recorte_completo:
        linhas = [
            r
            for r in linhas
            if not r["case"].get("metadata", {}).get("fonte_so_no_recorte_completo")
        ]
    ok = [r for r in linhas if r["attempt"]["state"] == "success"]
    fid = {id(r): fidelidade(r) for r in linhas}

    def score(nome):
        def f(r):
            s = r.get(nome) or {}
            return s.get("f1") if s.get("state") == "success" else None

        return f

    tempos = sorted(
        r["attempt"]["duration_seconds"]
        for r in ok
        if r["attempt"].get("duration_seconds") is not None
    )
    conc_resp, conc_fontes = _concordancia(linhas)
    julgadas = [r for r in linhas if r.get("judgment", "not_assessed") != "not_assessed"]
    completo = bool(linhas) and len(julgadas) == len(linhas)
    esclarecer = ("needs_clarification",)
    return {
        "perguntas": len({r["case"]["id"] for r in linhas}),
        "tentativas": len(linhas),
        "falhas": len(linhas) - len(ok),
        "rouge_l": _media_por_pergunta(linhas, score("rouge_l")),
        "bert_score": _media_por_pergunta(linhas, score("bert_score")),
        "artigo_esperado": _media_por_pergunta(linhas, lambda r: fid[id(r)]["artigo_esperado"]),
        "citacao_suportada": _media_por_pergunta(linhas, lambda r: fid[id(r)]["citacao_suportada"]),
        "clarify": _taxa(linhas, "clarify", esclarecer),
        "falso_positivo": _taxa(linhas, "answer", esclarecer),
        "recusa_fora_acervo": _taxa(linhas, "abstain", ("insufficient_context",)),
        # Automática: só o status do RAG. A recusa indevida de verdade exige a revisão humana.
        "recusa_indevida": _taxa(linhas, "answer", ("insufficient_context",)),
        # Só com TODAS as tentativas julgadas (adjudicação); senão, revisão humana pendente.
        "respostas_boas": sum(r["judgment"] == "correct" for r in julgadas) / len(julgadas)
        if completo
        else None,
        "respostas_erradas": sum(r["judgment"] == "incorrect" for r in julgadas)
        if completo
        else None,
        "lat_mediana": statistics.median(tempos) if tempos else None,
        "lat_p95": tempos[max(0, math.ceil(0.95 * len(tempos)) - 1)] if tempos else None,
        "conc_resposta": conc_resp,
        "conc_fontes": conc_fontes,
    }


def metricas_recuperacao(dados: dict, chave: str = "rodadas") -> dict:
    """Recall@8/MRR (estritos e lenientes) da camada reranker + norma citada."""
    linha = next((r for r in dados.get(chave, {}).get("rerank_norma", []) if r["top_k"] == 8), None)
    if linha is None:
        return dict.fromkeys(("recall8", "mrr8", "recall8_leniente", "mrr8_leniente"))
    return {
        "recall8": linha["recall_estrita"],
        "mrr8": linha["mrr_estrita"],
        "recall8_leniente": linha["recall_estrita_leniente"],
        "mrr8_leniente": linha["mrr_estrita_leniente"],
    }


# ---------------------------------------------------------------- tabela


def _valor(metrica):
    return metrica["taxa"] if isinstance(metrica, dict) else metrica


def _celula(chave, metrica, base):
    valor = _valor(metrica)
    texto = (
        "n/d"
        if valor is None
        else (
            f"{metrica['n']}/{metrica['total']}"
            if isinstance(metrica, dict)
            else (f"{valor:.0f}" if chave == "respostas_erradas" else f"{valor:.3f}")
        )
    )
    ok = None
    if valor is not None and chave in METAS:
        op, lim, _ = METAS[chave]
        ok = valor <= lim if op == "<=" else valor >= lim
    base_v = _valor(base) if base is not None else None
    delta = valor - base_v if valor is not None and base_v is not None else None
    if chave in NAO_PIORAR and delta is not None:
        ok = delta >= -1e-9
    return {"valor": valor, "texto": texto, "ok": ok, "delta": delta}


def montar_comparacao(resultados: dict, baseline: str) -> dict:
    """resultados: nome -> resultado.json. Devolve {recorte: {nome: {coluna: célula}}}."""
    saida = {"baseline": baseline, "recortes": {}}
    for recorte in RECORTE:
        linhas = {}
        for nome, res in resultados.items():
            m = {**res["avaliacao"][recorte], **res["recuperacao"][recorte]}
            base = (
                None
                if nome == baseline
                else (
                    {
                        **resultados[baseline]["avaliacao"][recorte],
                        **resultados[baseline]["recuperacao"][recorte],
                    }
                    if baseline in resultados
                    else None
                )
            )
            linhas[nome] = {
                c: _celula(c, m.get(c), base.get(c) if base else None) for c, _ in COLUNAS
            }
            linhas[nome]["_perguntas"] = m["perguntas"]
        saida["recortes"][recorte] = linhas
    return saida


def _fmt(v):
    return str(v).replace(".", ",")


def renderizar_markdown(comp: dict, dados_extra: dict | None = None) -> str:
    base = comp["baseline"]
    titulos = {
        "todos": "Todos os casos",
        "sem_recorte_completo": "Sem os casos com `fonte_so_no_recorte_completo`",
    }
    out = [f"# Comparação dos experimentos (linha de base: `{base}`)\n"]
    out.append(
        "Legenda: ✓ atinge a meta (§3.1 de metricas-avaliacao-rag.md), ✗ não atinge; ROUGE-L e BERTScore: "
        "✓ = não piorou em relação à linha de base. Entre parênteses, a diferença para a linha de base. "
        "`n/d` = precisa de revisão humana (revisao_independente.xlsx) ou não foi medido. "
        "Recusa indevida aqui é automática (status do RAG), indício a confirmar na revisão. "
        "Clarify e falso positivo contam tentativas (perguntas x repetições).\n"
    )
    for recorte in RECORTE:
        linhas = comp["recortes"][recorte]
        out.append(f"## {titulos[recorte]}\n")
        cab = ["Experimento", "Perguntas"] + [r for _, r in COLUNAS]
        meta = ["meta", ""] + [
            METAS[c][2] if c in METAS else ("≥ base" if c in NAO_PIORAR else "") for c, _ in COLUNAS
        ]
        out.append("| " + " | ".join(cab) + " |")
        out.append("|" + "---|" * len(cab))
        out.append("| " + " | ".join(meta) + " |")
        for nome, cels in linhas.items():
            partes = [f"**{nome}**" if nome == base else nome, str(cels["_perguntas"])]
            for c, _ in COLUNAS:
                cel = cels[c]
                s = _fmt(cel["texto"])
                if cel["ok"] is not None:
                    s += " ✓" if cel["ok"] else " ✗"
                if cel["delta"] is not None and nome != base:
                    s += " (" + _fmt(format(cel["delta"], "+.3f")) + ")"
                partes.append(s)
            out.append("| " + " | ".join(partes) + " |")
        out.append("")
    return "\n".join(out)


def carregar_resultados(saida: Path) -> dict:
    achados = {}
    for arq in sorted(saida.glob("*/resultado.json")):
        res = json.loads(arq.read_text(encoding="utf-8"))
        achados[res["nome"]] = res
    return achados


def gravar_tabela(saida: Path, baseline: str) -> Path | None:
    resultados = carregar_resultados(saida)
    if not resultados:
        return None
    if baseline not in resultados:
        print(
            f"AVISO: linha de base '{baseline}' sem resultado; tabela sem diferenças",
            file=sys.stderr,
        )
    comp = montar_comparacao(resultados, baseline)
    (saida / "comparacao.json").write_text(
        json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = saida / "comparacao.md"
    md.write_text(renderizar_markdown(comp), encoding="utf-8")
    return md


# ---------------------------------------------------------------- execução


def _relatorio_mais_novo(run_dir: Path) -> Path | None:
    achados = sorted(run_dir.glob("reports/*/*/results.json"), key=lambda p: p.stat().st_mtime)
    return achados[-1] if achados else None


def comando_avaliacao(
    cfg: dict, exp: dict, python: str, pasta: Path, extra: list[str], retomar: bool
) -> list[str]:
    cmd = [
        python, "-m", "evaluation", "run",
        "--dataset", str((RAIZ / cfg["conjunto"]).resolve()),
        "--run-dir", str((pasta / "avaliacao").resolve()),
        "--all", "--split", cfg["split"],
        "--rag-version", exp["nome"],
        "--corpus-version", exp["env_final"]["COLLECTION_NAME"],
        "--repeticoes", str(cfg["repeticoes"]),
        *extra,
    ]  # fmt: skip
    return cmd + (["--resume"] if retomar else [])


def comando_recuperacao(cfg: dict, python: str, pasta: Path) -> list[str]:
    return [
        python, str(RAIZ / "scripts" / "medir_recuperacao_qdrant.py"),
        "--gt", str((RAIZ / cfg["conjunto"]).resolve()),
        "--saida", str((pasta / "recuperacao.json").resolve()),
    ]  # fmt: skip


def _rodar(cmd: list[str], env: dict, cwd: Path, rotulo: str) -> None:
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env})
    if r.returncode != 0:
        raise ExperimentoAbortado(f"{rotulo} falhou (código {r.returncode})")


def executar(cfg: dict, exp: dict, saida: Path, python: str, extra_avaliacao: list[str]) -> Path:
    """Roda um experimento; devolve o caminho do resultado.json. Levanta ExperimentoAbortado."""
    pasta = saida / exp["nome"]
    pasta.mkdir(parents=True, exist_ok=True)
    env = exp["env_final"]
    conferir(env, settings_efetivas(python, env), "antes da avaliação")

    run_dir = pasta / "avaliacao"
    relatorio = _relatorio_mais_novo(run_dir)
    if relatorio is None:
        retomar = (run_dir / "checkpoints.sqlite3").exists()
        _rodar(
            comando_avaliacao(cfg, exp, python, pasta, extra_avaliacao, retomar),
            env,
            API,
            "avaliação",
        )
        relatorio = _relatorio_mais_novo(run_dir)
        if relatorio is None:
            raise ExperimentoAbortado("avaliação terminou sem relatório")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    conferir(env, manifest["rag_metadata"]["settings"], "manifest da execução")

    recuperacao = pasta / "recuperacao.json"
    if not recuperacao.exists():
        _rodar(comando_recuperacao(cfg, python, pasta), env, RAIZ, "medição de recuperação")
    rec = json.loads(recuperacao.read_text(encoding="utf-8"))
    if rec.get("colecao") != env["COLLECTION_NAME"]:
        raise ExperimentoAbortado(
            f"recuperação mediu {rec.get('colecao')!r}, esperado {env['COLLECTION_NAME']!r}"
        )

    linhas = json.loads(relatorio.read_text(encoding="utf-8"))
    resultado = {
        "nome": exp["nome"],
        "descricao": exp.get("descricao", ""),
        "env": env,
        "repeticoes": cfg["repeticoes"],
        "relatorio": str(relatorio),
        "avaliacao": {
            "todos": metricas_avaliacao(linhas, False),
            "sem_recorte_completo": metricas_avaliacao(linhas, True),
        },
        "recuperacao": {
            "todos": metricas_recuperacao(rec),
            "sem_recorte_completo": metricas_recuperacao(rec, "rodadas_sem_recorte_completo"),
        },
    }
    alvo = pasta / "resultado.json"
    alvo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return alvo


def imprimir_plano(
    cfg: dict, escolhidos: list[dict], saida: Path, python: str, extra: list[str]
) -> None:
    print(
        f"Saída: {saida}\nRepetições: {cfg['repeticoes']}  Conjunto: {cfg['conjunto']}  Baseline: {cfg['baseline']}"
    )
    for exp in escolhidos:
        pasta = saida / exp["nome"]
        feito = "  [já concluído, será pulado]" if (pasta / "resultado.json").exists() else ""
        print(f"\n== {exp['nome']}{feito}\n   {exp.get('descricao', '')}")
        print("   env: " + " ".join(f"{k}={v}" for k, v in sorted(exp["env_final"].items())))
        print("   1. conferir Settings() efetiva com esse env (aborta se divergir)")
        print("   2. " + " ".join(comando_avaliacao(cfg, exp, python, pasta, extra, False)))
        print("   3. conferir manifest.json da execução")
        print("   4. " + " ".join(comando_recuperacao(cfg, python, pasta)))
    print(f"\nTabela: {saida / 'comparacao.md'} e comparacao.json")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--so", help="nomes separados por vírgula (subconjunto)")
    p.add_argument("--repeticoes", type=int, help="sobrepõe 'repeticoes' da config")
    p.add_argument("--saida", type=Path, help="padrão: data/benchmark/experimentos-<data>")
    p.add_argument("--data", default=date.today().isoformat())
    p.add_argument("--python", default=sys.executable, help="interpretador com a API e a avaliação")
    p.add_argument(
        "--avaliacao-args",
        default="",
        help="argumentos extras do `evaluation run`, ex.: '--device cuda'",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="valida e mostra o plano, sem tocar nos serviços"
    )
    args = p.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):  # console cp1252 do Windows não imprime ✓/✗
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")

    try:
        cfg = carregar_config(args.config)
    except (ConfigInvalida, OSError, json.JSONDecodeError) as exc:
        print(f"Config inválida: {exc}", file=sys.stderr)
        return 2
    if args.repeticoes:
        cfg["repeticoes"] = args.repeticoes
    escolhidos = cfg["experimentos"]
    if args.so:
        nomes = [n.strip() for n in args.so.split(",") if n.strip()]
        desconhecidos = set(nomes) - {e["nome"] for e in escolhidos}
        if desconhecidos:
            print(f"--so com nomes desconhecidos: {sorted(desconhecidos)}", file=sys.stderr)
            return 2
        escolhidos = [e for e in escolhidos if e["nome"] in nomes]
    saida = args.saida or RAIZ / "data" / "benchmark" / f"experimentos-{args.data}"
    extra = args.avaliacao_args.split()

    if args.dry_run:
        imprimir_plano(cfg, escolhidos, saida, args.python, extra)
        return 0

    falhas = []
    for exp in escolhidos:
        if (saida / exp["nome"] / "resultado.json").exists():
            print(f"[{exp['nome']}] já concluído, pulando")
            continue
        print(f"[{exp['nome']}] iniciando")
        try:
            executar(cfg, exp, saida, args.python, extra)
        except ExperimentoAbortado as exc:
            print(f"[{exp['nome']}] ABORTADO: {exc}", file=sys.stderr)
            falhas.append(exp["nome"])
    tabela = gravar_tabela(saida, cfg["baseline"])
    if tabela:
        print(tabela.read_text(encoding="utf-8"))
    if falhas:
        print(f"Experimentos abortados: {', '.join(falhas)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
