"""
Script de Medição e Calibração de Parâmetros de Recuperação (Qdrant & VectorStore).
Sócio Digital — RES-IA Challenge 2 (Ciência de Dados - Jhessica).

Etapa 4 do Plano de Entrega:
- Compara a fonte esperada (expected_sources) com o document_id dos chunks recuperados.
- Calcula métricas oficiais: Recall@k, Precision@k e MRR (Mean Reciprocal Rank).
- Executa rodadas de calibração para TOP_K (3, 5, 8, 10) e SCORE_THRESHOLD (0.3, 0.4, 0.5, 0.6, 0.7).
- Exporta relatório de calibração em 'data/benchmark/calibracao_parametros_recuperacao.json'.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.rag.vector_store import LegalVectorStore


def _normalize_id(doc_id: str) -> str:
    """Normaliza identificadores como 'lc123' <-> 'leg-lc123'."""
    clean = doc_id.lower().replace("_", "-").replace("leg-", "")
    if clean.startswith("man-"):
        clean = clean[4:]
    return clean


def calculate_metrics_for_query(
    expected_sources: List[str],
    retrieved_doc_ids: List[str],
    k: int,
) -> tuple[float, float, float]:
    """
    Calcula Recall@k, Precision@k e Reciprocal Rank (RR).
    - Se expected_sources for vazio (ex.: guardrail/abstenção), considera 1.0 se não recuperou nada indevido.
    """
    if not expected_sources:
        return 1.0, 1.0, 1.0

    expected_norm = {_normalize_id(s) for s in expected_sources}
    retrieved_at_k = [_normalize_id(d) for d in retrieved_doc_ids[:k]]

    matched = expected_norm.intersection(set(retrieved_at_k))
    recall_at_k = len(matched) / len(expected_norm)
    precision_at_k = len(matched) / max(len(retrieved_at_k), 1)

    # Reciprocal Rank: posição do primeiro documento relevante (1 / rank)
    rr = 0.0
    for rank, doc_id in enumerate(retrieved_at_k, 1):
        if doc_id in expected_norm:
            rr = 1.0 / rank
            break

    return recall_at_k, precision_at_k, rr

    return recall_at_k, precision_at_k, rr


def run_benchmark_calibration(
    benchmark_path: str = "data/benchmark/ground_truth_25_perguntas.json",
    db_path: str = "data/processed/vector_index.db",
    output_path: str = "data/benchmark/calibracao_parametros_recuperacao.json",
    filter_behavior: Optional[str] = "answer",
):
    print("=" * 80)
    print(" SÓCIO DIGITAL — AVALIAÇÃO DE RECUPERAÇÃO E CALIBRAÇÃO DE PARÂMETROS")
    print(" Responsável: Jhessica (Ciência de Dados)")
    print("=" * 80)

    with open(benchmark_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if filter_behavior:
        eval_cases = [c for c in dataset if c.get("expected_behavior") == filter_behavior]
    else:
        eval_cases = dataset

    print(
        f"[*] Dataset carregado: {len(dataset)} casos ({len(eval_cases)} casos com comportamento '{filter_behavior}')"
    )

    store = LegalVectorStore(db_path=db_path, use_dense=True)

    top_k_options = [3, 5, 8, 10]
    threshold_options = [0.30, 0.40, 0.50, 0.60, 0.70]

    calibration_results = []

    print("\nIniciando rodadas de calibração cruzada de TOP_K e SCORE_THRESHOLD...")
    print("-" * 80)
    print(
        f"{'Rodada':<8} | {'TOP_K':<6} | {'Threshold':<10} | {'Recall@1':<10} | {'Recall@K':<10} | {'MRR':<10} | {'Status'}"
    )
    print("-" * 80)

    round_id = 1
    best_config = None
    best_mrr = -1.0

    for top_k in top_k_options:
        for thresh in threshold_options:
            recalls_1 = []
            recalls_k = []
            precisions_k = []
            reciprocal_ranks = []

            for case in eval_cases:
                expected = case.get("expected_sources", [])
                query = case["question"]

                hits = store.search(query=query, top_k=top_k)
                # Filtra por score_threshold
                filtered_hits = [h for h in hits if h["score"] >= thresh]
                retrieved_docs = [
                    h.get("document_id") for h in filtered_hits if h.get("document_id")
                ]

                r1, _, _ = calculate_metrics_for_query(expected, retrieved_docs, k=1)
                rk, pk, rr = calculate_metrics_for_query(expected, retrieved_docs, k=top_k)

                recalls_1.append(r1)
                recalls_k.append(rk)
                precisions_k.append(pk)
                reciprocal_ranks.append(rr)

            mean_recall_1 = sum(recalls_1) / len(recalls_1)
            mean_recall_k = sum(recalls_k) / len(recalls_k)
            mean_precision_k = sum(precisions_k) / len(precisions_k)
            mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)

            status = "EXCELENTE" if mrr >= 0.85 else ("BOM" if mrr >= 0.70 else "AJUSTAR")
            print(
                f"R{round_id:<7} | {top_k:<6} | {thresh:<10.2f} | {mean_recall_1 * 100:>8.1f}% | {mean_recall_k * 100:>8.1f}% | {mrr:>9.3f} | {status}"
            )

            config_entry = {
                "round": round_id,
                "top_k": top_k,
                "score_threshold": thresh,
                "recall_at_1": round(mean_recall_1, 4),
                "recall_at_k": round(mean_recall_k, 4),
                "precision_at_k": round(mean_precision_k, 4),
                "mrr": round(mrr, 4),
            }
            calibration_results.append(config_entry)

            if mrr > best_mrr:
                best_mrr = mrr
                best_config = config_entry

            round_id += 1

    print("-" * 80)
    print("\n[RECOMENDAÇÃO FINAL PARA O LUCAS]:")
    print(
        f"Melhor Configuração Calibrada: TOP_K = {best_config['top_k']} | SCORE_THRESHOLD = {best_config['score_threshold']}"
    )
    print(f" -> Recall@{best_config['top_k']}: {best_config['recall_at_k'] * 100:.1f}%")
    print(f" -> MRR (Mean Reciprocal Rank): {best_config['mrr']:.3f}")
    print(f" -> Recall@1: {best_config['recall_at_1'] * 100:.1f}%")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    summary_report = {
        "responsavel": "Jhessica (Ciência de Dados)",
        "frente": "Calibração e Medição de RAG",
        "benchmark_file": benchmark_path,
        "total_test_cases": len(eval_cases),
        "best_configuration": best_config,
        "rounds": calibration_results,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2, ensure_ascii=False)

    print(f"\n[*] Relatório de calibração exportado para: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Medição e calibração de parâmetros de RAG")
    parser.add_argument("--benchmark", default="data/benchmark/ground_truth_25_perguntas.json")
    parser.add_argument("--db", default="data/processed/vector_index.db")
    parser.add_argument("--output", default="data/benchmark/calibracao_parametros_recuperacao.json")
    args = parser.parse_args()

    run_benchmark_calibration(
        benchmark_path=args.benchmark,
        db_path=args.db,
        output_path=args.output,
    )
