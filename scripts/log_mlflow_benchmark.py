#!/usr/bin/env python3
"""
Script de Rastreamento de Métricas e Governança no MLflow.
Frente: Ops (DevOps & MLOps — Ingrid).
Projeto: Sócio Digital — RES-IA Challenge 2.

Finalidade:
    Registrar formalmente as métricas de qualidade de RAG, tempo de resposta,
    parâmetros de configuração e artefatos de auditoria no MLflow Tracking.
    Permite comparação histórica de experimentos e controle de versões do copiloto.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def logar_metricas_mlflow(results_path: Path, run_name: str = "rag_governance_benchmark"):
    if not results_path.exists():
        print(f"[ERRO] Arquivo de benchmark não encontrado em: {results_path}")
        return False

    with open(results_path, "r", encoding="utf-8") as f:
        try:
            results = json.load(f)
        except Exception as e:
            print(f"[ERRO] Falha ao ler JSON: {e}")
            return False

    try:
        import mlflow
    except ImportError:
        print("[AVISO] Pacote 'mlflow' não está instalado neste ambiente Python.")
        print("Para habilitar o envio ao servidor MLflow, instale via: pip install mlflow")
        print(
            f"[INFO] {results.get('total_cenarios', 0)} cenários avaliados com sucesso localmente."
        )
        return True

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlruns.db")
    mlflow.set_tracking_uri(tracking_uri)

    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "socio-digital-rag-governance")
    mlflow.set_experiment(experiment_name)

    print(f"[*] Conectando ao MLflow Tracking: {tracking_uri}")
    print(f"[*] Experimento: {experiment_name} | Run: {run_name}")

    with mlflow.start_run(run_name=run_name):
        # 1. Registrar Parâmetros e Metadados de Versão
        meta = results.get("metadados_versao", {})
        mlflow.log_param("frente", meta.get("frente", "Ciência de Dados (Jhessica)"))
        mlflow.log_param("projeto", meta.get("projeto", "Sócio Digital"))
        mlflow.log_param("versao_rag", meta.get("versao_rag", "2.0.0-factual-hybrid"))
        mlflow.log_param(
            "modelo_embeddings",
            meta.get("modelo_embeddings", "Qwen3-Embedding / SentenceTransformers"),
        )
        mlflow.log_param("total_cenarios", results.get("total_cenarios", 10))

        # 2. Registrar Métricas Quantitativas
        metricas = {
            "rag_context_recall": float(results.get("context_recall_medio", 0.0)),
            "rag_context_precision": float(results.get("context_precision_medio", 0.0)),
            "rag_faithfulness": float(results.get("faithfulness_medio", 0.0)),
            "rag_guardrail_robustness": float(results.get("guardrail_robustness", 0.0)),
            "rag_conformidade_3_passos": float(results.get("conformidade_3_passos", 0.0)),
            "rag_conformidade_crc": float(results.get("conformidade_crc", 0.0)),
            "rag_taxa_aprovacao_global": float(results.get("taxa_aprovacao_global", 0.0)),
            "rag_latency_avg_ms": float(results.get("tempo_medio_ms", 0.0)),
            "rag_latency_total_ms": float(results.get("tempo_total_ms", 0.0)),
        }

        for k, v in metricas.items():
            mlflow.log_metric(k, v)

        # 3. Anexar Artefato do Benchmark
        mlflow.log_artifact(str(results_path))

    print("[SUCESSO] Métricas de governança e fidelidade registradas no MLflow com êxito!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Registro de métricas de benchmark RAG no MLflow.")
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "data"
        / "benchmark"
        / "benchmark_results.json",
        help="Caminho do arquivo benchmark_results.json.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default="rag_ci_quality_gate",
        help="Nome da execução no MLflow.",
    )
    args = parser.parse_args()

    ok = logar_metricas_mlflow(args.results, run_name=args.run_name)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
