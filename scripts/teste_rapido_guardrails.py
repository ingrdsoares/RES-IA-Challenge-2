"""Teste curto dos guardrails: só as perguntas que importam, 1 repetição, sem ROUGE/BERT.

    cd backend/api
    QDRANT_URL=http://127.0.0.1:6334 COLLECTION_NAME=knowledge_base_v2 RERANKER_URL=http://127.0.0.1:8080 \
    PYTHONPATH=. python ../../scripts/teste_rapido_guardrails.py --saida ../../data/benchmark/teste_rapido_guardrails.json

Seleção: perguntas que o sistema com guardrails errou de comportamento (falso positivo e recusa
indevida), todas as de clarify e de abstenção, as que perderam artigo e um controle aleatório.
Mede status e artigo_esperado por configuração; é um filtro rápido, não substitui a avaliação completa.
"""

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from app.config import Settings
from app.models import LocalModels
from app.rag import RagService
from app.vector_store import VectorStore
from evaluation.metrics.fidelidade import artigo_esperado
from evaluation.schemas import EvalCase

CONJUNTO = Path(__file__).resolve().parent.parent / "backend/evaluation/data/teste_ampliado_2026-11-12.jsonl"
# Perguntas de comportamento "answer" que a base errou (falta de artigo) ou que os guardrails afetaram.
PROBLEMA = {
    "ap04_simples_livro_caixa", "tr04_ibs_cbs_2026_teste", "rf01_extincao_icms_iss", "tr05_mei_limite_confuso",
    "ct01_acessoria_vira_principal", "icms03_restaurante", "jur02_carf_stf_art17v",
    "jur03_carf_debitos_simples_federal", "iss01_relacao_emprego", "lp01_presuncao_combustivel",
    # falso positivo e recusa indevida dos guardrails (revisados um a um)
    "ap03_simples_debito_art17", "icms02_credito_veiculo_pessoal", "jur01_carf_mei_cnae", "mei05_dasn_extincao",
    "mei06_valor_mes_da_baixa", "mei07_beneficios_formalizacao", "mei08_restituicao_inss_beneficio",
}
CONFIGS = {
    "referencia": {},
    "topk10": {"top_k": 10},
    "retry": {"retry_recusa": True},
    "raciocinio": {"esclarecimento_raciocinio": True},
    "combinado": {"top_k": 10, "retry_recusa": True, "esclarecimento_raciocinio": True},
    "slots4": {"citation_slots": 4},
    "slots6": {"citation_slots": 6},
    "slots10": {"citation_slots": 10},
}
BASE = {"guardrails_texto": True, "esclarecimento_modelo": True}


def selecionar() -> list[EvalCase]:
    casos = [EvalCase.model_validate(json.loads(l)) for l in CONJUNTO.read_text(encoding="utf-8").splitlines() if l.strip()]
    por_id = {c.id: c for c in casos}
    sel = {c.id for c in casos if c.expected_behavior in ("clarify", "abstain")} | (PROBLEMA & por_id.keys())
    resto = [c.id for c in casos if c.expected_behavior == "answer" and c.id not in sel]
    random.Random(42).shuffle(resto)
    sel |= set(resto[:15])  # controle: onde um falso positivo novo apareceria
    return [por_id[i] for i in por_id if i in sel and por_id[i].split in ("final", "development")]


def rodar(nome: str, extra: dict, casos: list[EvalCase]) -> dict:
    s = Settings(**BASE, **extra)
    svc = RagService(s, VectorStore(s), LocalModels(s))
    linhas = []
    for c in casos:
        t0 = time.perf_counter()
        r = svc.query(c.question)
        dt = time.perf_counter() - t0
        att = type("A", (), {"state": "success", "rag_status": r.status, "sources": [x.model_dump() for x in r.sources]})
        a = artigo_esperado(c, att)
        linhas.append({"id": c.id, "esperado": c.expected_behavior, "status": r.status, "seg": dt,
                       "artigo": a.precision if a.state == "success" else None})
        print(f"{nome:11s} {c.expected_behavior:8s} {r.status:20s} {c.id}", flush=True)
    svc.close()
    ans = [l for l in linhas if l["esperado"] == "answer"]
    cla = [l for l in linhas if l["esperado"] == "clarify"]
    abs_ = [l for l in linhas if l["esperado"] == "abstain"]
    arts = [l["artigo"] for l in ans if l["artigo"] is not None]
    return {
        "falso_positivo": f"{sum(l['status'] == 'needs_clarification' for l in ans)}/{len(ans)}",
        "recusa_indevida": f"{sum(l['status'] == 'insufficient_context' for l in ans)}/{len(ans)}",
        "clarify": f"{sum(l['status'] == 'needs_clarification' for l in cla)}/{len(cla)}",
        "abstencao": f"{sum(l['status'] == 'insufficient_context' for l in abs_)}/{len(abs_)}",
        "artigo_esperado": round(sum(arts) / len(arts), 3) if arts else None,
        "mediana_s": round(statistics.median(l["seg"] for l in linhas), 2),
        "linhas": linhas,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--saida", required=True)
    p.add_argument("--configs", default=",".join(CONFIGS))
    a = p.parse_args()
    casos = selecionar()
    print(f"{len(casos)} perguntas")
    res = {n: rodar(n, CONFIGS[n], casos) for n in a.configs.split(",")}
    Path(a.saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'config':11s} {'FP':>6s} {'indevida':>9s} {'clarify':>8s} {'abstencao':>10s} {'artigo':>7s} {'mediana':>8s}")
    for n, r in res.items():
        print(f"{n:11s} {r['falso_positivo']:>6s} {r['recusa_indevida']:>9s} {r['clarify']:>8s} {r['abstencao']:>10s} {r['artigo_esperado']!s:>7s} {r['mediana_s']:>7}s")


if __name__ == "__main__":
    main()
