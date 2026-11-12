"""Calibra o SCORE_THRESHOLD (cosseno denso) na base atual do Qdrant.

Para cada pergunta do dataset guarda o maior score denso (sem limiar) e, para cada limiar
candidato, mede:
- perda_in_scope: parcela das perguntas answer (com expected_sources) que ficariam SEM
  nenhum trecho (maior score < limiar);
- vazamento_out_of_scope: parcela das perguntas abstain que ainda receberiam contexto
  (maior score >= limiar).
Perguntas clarify ficam de fora das duas contas (só são contadas no resumo).

Recomendado: o maior limiar com perda in-scope zero; os limiares vizinhos com o mesmo
vazamento (empate) são listados. Não altera a configuração: o valor só muda após a rodada real.

Uso (Qdrant e Ollama no ar):
  python scripts/calibrar_limiar.py --dataset backend/evaluation/data/ground_truth_avaliacao.jsonl \
      --saida data/benchmark/calibracao_limiar.json [--min 0.40 --max 0.65 --passo 0.01]
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend" / "api"))


def calcular(casos: list[dict], limiares: list[float]) -> dict:
    """casos: dicts com 'comportamento' (answer/abstain/clarify), 'tem_fonte' e 'top_score'."""
    dentro = [c["top_score"] for c in casos if c["comportamento"] == "answer" and c["tem_fonte"]]
    fora = [c["top_score"] for c in casos if c["comportamento"] == "abstain"]
    linhas = []
    for t in limiares:
        linhas.append(
            {
                "limiar": round(t, 4),
                "perda_in_scope": sum(s < t for s in dentro) / len(dentro) if dentro else None,
                "vazamento_out_of_scope": sum(s >= t for s in fora) / len(fora) if fora else None,
            }
        )
    sem_perda = [x for x in linhas if x["perda_in_scope"] == 0]
    recomendado, empate = None, []
    if sem_perda:
        recomendado = max(x["limiar"] for x in sem_perda)
        vaza = next(x for x in sem_perda if x["limiar"] == recomendado)["vazamento_out_of_scope"]
        # ponytail: empate = limiares sem perda e mesmo vazamento; não olha margem de segurança
        empate = [x["limiar"] for x in sem_perda if x["vazamento_out_of_scope"] == vaza]
    return {
        "n_in_scope": len(dentro),
        "n_out_of_scope": len(fora),
        "n_clarify": sum(c["comportamento"] == "clarify" for c in casos),
        "linhas": linhas,
        "recomendado": recomendado,
        "empate": empate,
    }


def _verificar() -> None:
    casos = [
        {"comportamento": "answer", "tem_fonte": True, "top_score": 0.70},
        {"comportamento": "answer", "tem_fonte": True, "top_score": 0.56},
        {"comportamento": "abstain", "tem_fonte": False, "top_score": 0.53},
        {"comportamento": "abstain", "tem_fonte": False, "top_score": 0.40},
        {"comportamento": "clarify", "tem_fonte": True, "top_score": 0.10},
    ]
    r = calcular(casos, [0.5, 0.55, 0.57, 0.6])
    por = {x["limiar"]: x for x in r["linhas"]}
    assert (por[0.5]["perda_in_scope"], por[0.5]["vazamento_out_of_scope"]) == (0.0, 0.5)
    assert (por[0.55]["perda_in_scope"], por[0.55]["vazamento_out_of_scope"]) == (0.0, 0.0)
    assert por[0.57]["perda_in_scope"] == 0.5
    assert r["recomendado"] == 0.55 and r["empate"] == [0.55]
    assert r["n_clarify"] == 1 and (r["n_in_scope"], r["n_out_of_scope"]) == (2, 2)


def main() -> int:
    from app.config import Settings
    from app.models import LocalModels
    from app.vector_store import VectorStore

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--saida", type=Path, default=RAIZ / "data/benchmark/calibracao_limiar.json")
    p.add_argument("--min", type=float, default=0.40)
    p.add_argument("--max", type=float, default=0.65)
    p.add_argument("--passo", type=float, default=0.01)
    args = p.parse_args()

    texto = args.dataset.read_text(encoding="utf-8")
    brutos = (
        [json.loads(x) for x in texto.splitlines() if x.strip()]
        if args.dataset.suffix == ".jsonl"
        else json.loads(texto)
    )
    settings = Settings()
    modelos, store = LocalModels(settings), VectorStore(settings)
    casos = []
    for c in brutos:
        vetor = modelos.embed_question(c["question"])
        hits = store._densa(vetor, settings.candidate_k, limiar=False)
        casos.append(
            {
                "id": c["id"],
                "comportamento": c.get("expected_behavior", "answer"),
                "tem_fonte": bool(c.get("expected_sources")),
                "top_score": round(max((h.score for h in hits), default=0.0), 4),
            }
        )
    n = round((args.max - args.min) / args.passo)
    resultado = calcular(casos, [args.min + i * args.passo for i in range(n + 1)])
    resultado |= {
        "colecao": settings.collection_name,
        "embedding": settings.embedding_model,
        "limiar_atual": settings.score_threshold,
        "dataset": str(args.dataset),
        "por_pergunta": casos,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    def pct(v):
        return "   n/a" if v is None else f"{v * 100:5.1f}%"

    print(f"{'limiar':>7} | {'perda in-scope':>14} | {'vazamento out':>13}")
    for x in resultado["linhas"]:
        print(
            f"{x['limiar']:>7.2f} | {pct(x['perda_in_scope']):>14} | {pct(x['vazamento_out_of_scope']):>13}"
        )
    print(
        f"Recomendado: {resultado['recomendado']} (empate: {resultado['empate']}); atual: {settings.score_threshold}"
    )
    return 0


if __name__ == "__main__":
    _verificar()
    sys.exit(main())
