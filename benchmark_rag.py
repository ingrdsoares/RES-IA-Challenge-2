#!/usr/bin/env python3
"""
Script de Execução de Benchmark e Métricas de Governança de RAG (MLOps).
Frente: Ciência de Dados (Jhessica).
Projeto: Sócio Digital — RES-IA Challenge 2.

Uso:
    python3 benchmark_rag.py
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.rag.evaluator import RAGEvaluator, BenchmarkSummary


def format_table_row(cols, widths, alignments=None):
    """Formata uma linha tabular com largura fixa e alinhamento."""
    if alignments is None:
        alignments = ["<"] * len(cols)
    out = []
    for val, w, align in zip(cols, widths, alignments):
        s = str(val)
        if len(s) > w:
            s = s[:w - 1] + "…"
        if align == ">":
            out.append(s.rjust(w))
        elif align == "^":
            out.append(s.center(w))
        else:
            out.append(s.ljust(w))
    return " | ".join(out)


def main():
    print("=" * 88)
    print("         SÓCIO DIGITAL — SUÍTE DE BENCHMARK QUANTITATIVO DE RAG (MLOps)         ")
    print("                     Frente: Ciência de Dados (Jhessica)                        ")
    print("=" * 88)

    ground_truth_file = ROOT_DIR / "data" / "benchmark" / "rag_ground_truth.json"
    results_json_file = ROOT_DIR / "data" / "benchmark" / "benchmark_results.json"

    print(f"[*] Dataset Ground Truth : {ground_truth_file}")
    print(f"[*] Exportação MLOps     : {results_json_file}\n")

    evaluator = RAGEvaluator(base_dir=ROOT_DIR)
    summary: BenchmarkSummary = evaluator.executar_benchmark(
        ground_truth_path=ground_truth_file,
        export_json_path=results_json_file,
    )

    # Tabela detalhada de cenários
    widths = [26, 18, 8, 8, 8, 6, 6, 9, 8]
    aligns = ["<", "<", ">", ">", ">", "^", "^", ">", "^"]
    headers = ["Cenário ID", "Categoria", "Recall", "Precis", "Faith", "3Step", "CRC", "Tempo", "Status"]

    print("-" * 88)
    print(format_table_row(headers, widths, aligns))
    print("-" * 88)

    for c in summary.cenarios:
        status_str = "[PASS]" if c.aprovado else "[FAIL]"
        row = [
            c.id,
            c.categoria,
            f"{c.context_recall * 100:.0f}%",
            f"{c.context_precision * 100:.0f}%",
            f"{c.faithfulness * 100:.0f}%",
            "SIM" if c.plano_3_passos_ok else "NÃO",
            "SIM" if c.crc_disclaimer_ok else "NÃO",
            f"{c.tempo_execucao_ms:.1f}ms",
            status_str,
        ]
        print(format_table_row(row, widths, aligns))

    print("-" * 88)

    # Painel Consolidado de Governança
    print("\n" + "=" * 88)
    print("                    PAINEL CONSOLIDADO DE MÉTRICAS (MLOps)                      ")
    print("=" * 88)

    def print_metric(nome: str, valor: float, meta: float, formato: str = "{:.1f}%"):
        atingiu = valor >= meta
        status = "APROVADO" if atingiu else "REPROVADO"
        v_str = formato.format(valor * 100 if "%" in formato else valor)
        m_str = formato.format(meta * 100 if "%" in formato else meta)
        print(f"  • {nome.ljust(35)}: {v_str.rjust(8)}  (Meta: >= {m_str}) -> [{status}]")

    print_metric("Context Recall Global (Top K)", summary.context_recall_medio, 0.90)
    print_metric("Context Precision Global (Top 1)", summary.context_precision_medio, 0.85)
    print_metric("Faithfulness (Zero Alucinação)", summary.faithfulness_medio, 0.99)
    print_metric("Guardrail Robustness (Abstenção)", summary.guardrail_robustness, 1.00)
    print_metric("Taxa de Conformidade RF07 (3 Passos)", summary.conformidade_3_passos, 1.00)
    print_metric("Taxa de Presença Disclaimer CRC", summary.conformidade_crc, 1.00)
    print(f"  • {'Tempo Médio por Consulta'.ljust(35)}: {f'{summary.tempo_medio_ms:.2f}ms'.rjust(8)}  (Benchmark Latência)")
    print(f"  • {'Tempo Total de Execução'.ljust(35)}: {f'{summary.tempo_total_ms:.2f}ms'.rjust(8)}  ({summary.total_cenarios} cenários)")
    print(f"  • {'Taxa Global de Aprovação'.ljust(35)}: {f'{summary.taxa_aprovacao_global * 100:.1f}%'.rjust(8)}  ({summary.total_aprovados}/{summary.total_cenarios} cenários)")

    print("=" * 88)

    if summary.todos_aprovados:
        print("\n>>> RESULTADO FINAL: TODOS OS CRITÉRIOS DE ACEITAÇÃO FORAM ATINGIDOS COM SUCESSO! <<<")
        print(">>> Artefato de governança pronto para ingestão no MLflow e esteira CI/CD da Ingrid. <<<\n")
        sys.exit(0)
    else:
        print("\n[ERRO] Um ou mais cenários falharam nos critérios de aceitação.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
