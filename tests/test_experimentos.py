"""Testes offline de scripts/experimentos.py: sem serviços; subprocess e relatórios falsos."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("experimentos", RAIZ / "scripts" / "experimentos.py")
exp = importlib.util.module_from_spec(spec)
sys.modules["experimentos"] = exp
spec.loader.exec_module(exp)

COLECAO = {"COLLECTION_NAME": "knowledge_base_v2"}


def _cfg(tmp_path, **mudancas):
    cfg = {
        "baseline": "base",
        "repeticoes": 2,
        "experimentos": [
            {"nome": "base", "env": COLECAO},
            {"nome": "cand60", "env": COLECAO | {"CANDIDATE_K": 60}},
        ],
    } | mudancas
    arq = tmp_path / "cfg.json"
    arq.write_text(json.dumps(cfg))
    return arq


def test_exemplo_valido_e_completo():
    cfg = exp.carregar_config(RAIZ / "data/benchmark/experimentos.exemplo.json")
    nomes = [e["nome"] for e in cfg["experimentos"]]
    assert cfg["baseline"] == "base_v2" and len(nomes) == len(set(nomes))
    assert {
        "v4a_janela_1500",
        "v4e_corte_por_artigo",
        "esclarecimento_modelo",
        "conferir_citacoes",
    } <= set(nomes)
    base = cfg["experimentos"][0]["env_final"]
    assert base["CANDIDATE_K"] == "30" and base["ESCLARECIMENTO_MODELO"] == "false"


def test_env_final_mescla_padroes(tmp_path):
    env = exp.carregar_config(_cfg(tmp_path))["experimentos"][1]["env_final"]
    assert env["CANDIDATE_K"] == "60" and env["MAX_TRECHOS_POR_DOCUMENTO"] == "0"


@pytest.mark.parametrize(
    "mudanca",
    [
        {"baseline": "nao_existe"},
        {"repeticoes": 0},
        {"experimentos": []},
        {"experimentos": [{"nome": "a b", "env": COLECAO}]},
        {"experimentos": [{"nome": "a", "env": {}}]},
        {"experimentos": [{"nome": "a", "env": COLECAO | {"candidate_k": 1}}]},
        {"experimentos": [{"nome": "base", "env": COLECAO}] * 2},
    ],
)
def test_config_invalida(tmp_path, mudanca):
    with pytest.raises(exp.ConfigInvalida):
        exp.carregar_config(_cfg(tmp_path, **mudanca))


def test_divergencias():
    efetivo = {
        "candidate_k": 30,
        "esclarecimento_modelo": False,
        "reranker_url": None,
        "legislation_boost": 0.2,
    }
    ok = {
        "CANDIDATE_K": "30",
        "ESCLARECIMENTO_MODELO": "false",
        "RERANKER_URL": "",
        "LEGISLATION_BOOST": "0.2",
    }
    assert exp.divergencias(ok, efetivo) == []
    erros = exp.divergencias(
        {"CANDIDATE_K": "60", "ESCLARECIMENTO_MODELO": "true", "CONFERIR_CITACOES": "true"}, efetivo
    )
    assert len(erros) == 3 and "ignorada" in erros[2]


def test_env_divergente_aborta_antes_de_avaliar(tmp_path, monkeypatch):
    cfg = exp.carregar_config(_cfg(tmp_path))
    chamadas = []

    def falso(cmd, **kw):  # Settings efetivas ignoraram CANDIDATE_K=60
        chamadas.append(cmd)
        saida = json.dumps({"collection_name": "knowledge_base_v2", "candidate_k": 30})
        return subprocess.CompletedProcess(cmd, 0, stdout=saida, stderr="")

    monkeypatch.setattr(exp.subprocess, "run", falso)
    with pytest.raises(exp.ExperimentoAbortado, match="CANDIDATE_K"):
        exp.executar(cfg, cfg["experimentos"][1], tmp_path / "saida", "python", [])
    assert len(chamadas) == 1  # só leu Settings; nem avaliação nem recuperação
    assert not (tmp_path / "saida" / "cand60" / "resultado.json").exists()


def _linha(id_, comportamento, status, dur, rouge=0.5, recorte=False, rep=1):
    return {
        "case": {"id": id_, "expected_behavior": comportamento,
                 "metadata": {"fonte_so_no_recorte_completo": True} if recorte else {}},
        "attempt": {"state": "success", "rag_status": status, "duration_seconds": dur, "answer": "ok",
                    "sources": [{"chunk_id": "a"}], "repeat_index": rep},
        "rouge_l": {"state": "success", "f1": rouge},
        "bert_score": {"state": "success", "f1": 0.6},
        "judgment": "not_assessed",
    }  # fmt: skip


def _linhas():
    L = []
    for r in (1, 2):
        L += [
            _linha("a1", "answer", "answered", 2.0, 0.4, rep=r),
            _linha("a2", "answer", "needs_clarification", 3.0, 0.2, rep=r),  # falso positivo
            _linha("a3", "answer", "answered", 9.0, 0.9, recorte=True, rep=r),
            _linha("c1", "clarify", "needs_clarification", 1.0, rep=r),
            _linha("c2", "clarify", "answered", 1.0, rep=r),
            _linha("b1", "abstain", "insufficient_context", 1.0, rep=r),
        ]
    L[0]["attempt"]["answer"] = "diferente"  # a1 discorda entre as repetições
    return L


def _sem_fid(linha):
    return {"artigo_esperado": 1.0, "citacao_suportada": 0.5}


def test_metricas_todos_e_sem_recorte_completo():
    todos = exp.metricas_avaliacao(_linhas(), False, _sem_fid)
    sem = exp.metricas_avaliacao(_linhas(), True, _sem_fid)
    assert (todos["perguntas"], sem["perguntas"]) == (6, 5)  # a3 sai
    assert todos["rouge_l"] == pytest.approx((0.4 + 0.2 + 0.9 + 0.5 * 3) / 6)
    assert sem["rouge_l"] == pytest.approx((0.4 + 0.2 + 0.5 * 3) / 5)
    assert (todos["lat_mediana"], todos["lat_p95"], sem["lat_p95"]) == (1.5, 9.0, 3.0)
    assert todos["clarify"] == {"n": 2, "total": 4, "taxa": 0.5}
    assert todos["falso_positivo"]["total"] == 6 and sem["falso_positivo"] == {
        "n": 2,
        "total": 4,
        "taxa": 0.5,
    }
    assert sem["recusa_fora_acervo"]["taxa"] == 1.0 and sem["recusa_indevida"]["n"] == 0
    assert sem["conc_resposta"] == pytest.approx((0.5 + 4) / 5) and sem["conc_fontes"] == 1.0
    assert sem["respostas_boas"] is None  # sem julgamento: revisão humana


def test_fidelidade_real_nas_linhas():
    """Usa evaluation.metrics.fidelidade de verdade: resposta citando artigo que a fonte não traz."""
    linha = {
        "case": {"id": "x", "category": "c", "question": "pergunta qualquer?", "ground_truth": "Art. 3º da LC 123/2006.",
                 "expected_behavior": "answer"},
        "attempt": {"case_id": "x", "repeat_index": 1, "state": "success", "rag_status": "answered",
                    "answer": "Veja o art. 99 da LC 123/2006 [1].",
                    "sources": [{"title": "LC 123/2006", "text": "Art. 3º Consideram-se microempresas..."}]},
    }  # fmt: skip
    f = exp._fidelidade(linha)
    assert f["artigo_esperado"] == 1.0 and f["citacao_suportada"] == 0.5


def test_metricas_recuperacao():
    dados = {"rodadas": {"rerank_norma": [{"top_k": 3}, {"top_k": 8, "recall_estrita": 0.5, "mrr_estrita": 0.4,
             "recall_estrita_leniente": 0.6, "mrr_estrita_leniente": 0.45}]}}  # fmt: skip
    assert exp.metricas_recuperacao(dados)["recall8_leniente"] == 0.6
    assert exp.metricas_recuperacao(dados, "rodadas_sem_recorte_completo")["mrr8"] is None


def _resultado(nome, **aval):
    base = exp.metricas_avaliacao(_linhas(), False, _sem_fid) | aval
    rec = {"recall8": 0.5, "mrr8": 0.5, "recall8_leniente": 0.85, "mrr8_leniente": 0.6}
    return {"nome": nome, "avaliacao": {"todos": base, "sem_recorte_completo": base},
            "recuperacao": {"todos": rec, "sem_recorte_completo": rec}}  # fmt: skip


def test_tabela_metas_e_diferencas():
    melhor = {"rouge_l": 0.9, "citacao_suportada": 0.97, "lat_p95": 20.0}
    comp = exp.montar_comparacao(
        {"base": _resultado("base"), "x": _resultado("x", **melhor)}, "base"
    )
    x = comp["recortes"]["todos"]["x"]
    assert x["rouge_l"]["ok"] is True and x["rouge_l"]["delta"] > 0
    assert x["citacao_suportada"]["ok"] is True and x["lat_p95"]["ok"] is False
    assert x["recall8_leniente"]["ok"] is True and x["mrr8_leniente"]["ok"] is False
    assert x["respostas_boas"]["texto"] == "n/d" and x["respostas_boas"]["ok"] is None
    assert comp["recortes"]["todos"]["base"]["rouge_l"]["delta"] is None
    md = exp.renderizar_markdown(comp)
    assert "Sem os casos" in md and "✓" in md and "✗" in md and "**base**" in md


def test_dry_run_nao_toca_servicos(tmp_path, monkeypatch, capsys):
    def proibido(*a, **k):
        raise AssertionError("subprocess no dry-run")

    monkeypatch.setattr(exp.subprocess, "run", proibido)
    saida = str(tmp_path / "s")
    assert (
        exp.main(["--config", str(_cfg(tmp_path)), "--dry-run", "--so", "cand60", "--saida", saida])
        == 0
    )
    out = capsys.readouterr().out
    assert "CANDIDATE_K=60" in out and "== base" not in out
    assert exp.main(["--config", str(_cfg(tmp_path)), "--dry-run", "--so", "xx"]) == 2


def test_fluxo_completo_e_retomada(tmp_path, monkeypatch):
    cfg_arq = _cfg(tmp_path, experimentos=[{"nome": "base", "env": COLECAO}])
    # Settings fiel ao pedido: todos os campos do env padrão da linha de base
    base = exp.carregar_config(cfg_arq)["experimentos"][0]["env_final"]
    settings = {k.lower(): v for k, v in base.items()}
    chamadas = []

    def falso(cmd, cwd=None, env=None, **kw):
        chamadas.append(cmd)
        if "-c" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(settings), stderr="")
        if "--rag-version" in cmd:  # avaliação
            run = Path(cmd[cmd.index("--run-dir") + 1])
            (run / "reports" / "fp" / "h").mkdir(parents=True)
            (run / "reports" / "fp" / "h" / "results.json").write_text(json.dumps(_linhas()))
            (run / "manifest.json").write_text(json.dumps({"rag_metadata": {"settings": settings}}))
        else:  # recuperação
            rod = [{"top_k": 8, "recall_estrita": 0.5, "mrr_estrita": 0.4,
                    "recall_estrita_leniente": 0.6, "mrr_estrita_leniente": 0.5}]  # fmt: skip
            dados = {"colecao": "knowledge_base_v2", "rodadas": {"rerank_norma": rod},
                     "rodadas_sem_recorte_completo": {"rerank_norma": rod}}  # fmt: skip
            Path(cmd[cmd.index("--saida") + 1]).write_text(json.dumps(dados))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(exp.subprocess, "run", falso)
    monkeypatch.setattr(exp, "_fidelidade", _sem_fid)
    saida = tmp_path / "saida"
    argv = ["--config", str(cfg_arq), "--saida", str(saida), "--python", "py"]
    assert exp.main(argv) == 0
    res = json.loads((saida / "base" / "resultado.json").read_text())
    assert res["avaliacao"]["sem_recorte_completo"]["perguntas"] == 5
    assert res["recuperacao"]["todos"]["recall8_leniente"] == 0.6
    assert (saida / "comparacao.md").exists() and (saida / "comparacao.json").exists()
    antes = len(chamadas)
    assert exp.main(argv) == 0 and len(chamadas) == antes  # concluído: nada é rodado de novo
