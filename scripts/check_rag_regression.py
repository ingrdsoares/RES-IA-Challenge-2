#!/usr/bin/env python3
"""
Script de Verificação de Limites de Regressão de Qualidade do RAG (Quality Gate).
Frente: Ops (DevOps & MLOps — Ingrid).
Projeto: Sócio Digital — RES-IA Challenge 2.

Finalidade:
    Avaliar as métricas consolidadas em `data/benchmark/benchmark_results.json`
    contra os limiares mínimos de qualidade acordados pela equipe (Issue E2.7).
    Garante que nenhuma regressão em fidelidade, recuperação ou conformidade ética
    seja integrada à branch principal via Pull Request.

Critérios de Aceite:
    1. Job de qualidade no workflow do CI.
    2. Limite de regressão formalmente definido e documentado.
    3. Retorno com código POSIX: 0 (Aprovado) e 1 (Regressão detectada).
"""

import argparse
import json
import sys
from pathlib import Path

# Limiares canônicos de qualidade acordados para o Sócio Digital (Quality Gate)
DEFAULT_THRESHOLDS = {
    "context_recall_medio": {
        "min": 0.90,
        "nome": "Context Recall Global (Top K)",
        "formato": "percentual",
    },
    "context_precision_medio": {
        "min": 0.85,
        "nome": "Context Precision Global (Top 1)",
        "formato": "percentual",
    },
    "faithfulness_medio": {
        "min": 0.99,
        "nome": "Faithfulness (Zero Alucinação)",
        "formato": "percentual",
    },
    "guardrail_robustness": {
        "min": 1.00,
        "nome": "Guardrail Robustness (Abstenção Ética)",
        "formato": "percentual",
    },
    "conformidade_3_passos": {
        "min": 1.00,
        "nome": "Taxa de Conformidade RF07 (3 Passos)",
        "formato": "percentual",
    },
    "conformidade_crc": {
        "min": 1.00,
        "nome": "Taxa de Presença Disclaimer CRC",
        "formato": "percentual",
    },
    "taxa_aprovacao_global": {
        "min": 1.00,
        "nome": "Taxa Global de Aprovação dos Cenários",
        "formato": "percentual",
    },
    "tempo_medio_ms": {
        "max": 500.0,
        "nome": "Tempo Médio por Consulta (Latência RNF08)",
        "formato": "ms",
    },
}


def verificar_regressao(results_path: Path, thresholds: dict) -> bool:
    if not results_path.exists():
        print(f"[ERRO] Arquivo de resultados não encontrado: {results_path}")
        print("Certifique-se de executar 'python3 benchmark_rag.py' antes desta verificação.")
        return False

    with open(results_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"[ERRO] Falha ao decodificar JSON em {results_path}: {e}")
            return False

    print("=" * 80)
    print(" SÓCIO DIGITAL — AUDITORIA DE REGRESSÃO DE QUALIDADE RAG (CI/CD QUALITY GATE)")
    print(" Frente: Ops (DevOps & MLOps — Ingrid)")
    print("=" * 80)
    print(f"[*] Arquivo auditado: {results_path}")
    print(f"[*] Total de cenários avaliados: {data.get('total_cenarios', 'N/D')}\n")

    reprovado = False
    falhas = []

    print("-" * 80)
    print(f"{'Métrica':<40} | {'Obtido':>10} | {'Limiar Mín/Máx':>15} | {'Status':^8}")
    print("-" * 80)

    for chave, regra in thresholds.items():
        valor = data.get(chave)
        nome = regra["nome"]
        formato = regra.get("formato", "percentual")

        if valor is None:
            status = "[FALTA]"
            reprovado = True
            falhas.append(f"Métrica '{chave}' não encontrada nos resultados.")
            str_valor = "N/D"
            str_limite = "N/D"
        else:
            if formato == "percentual":
                str_valor = f"{valor * 100:.1f}%"
            elif formato == "ms":
                str_valor = f"{valor:.2f}ms"
            else:
                str_valor = str(valor)

            if "min" in regra:
                limite_min = regra["min"]
                str_limite = (
                    f">= {limite_min * 100:.1f}%" if formato == "percentual" else f">= {limite_min}"
                )
                if valor < limite_min:
                    status = "[REPROV]"
                    reprovado = True
                    falhas.append(f"{nome}: obtido {str_valor} abaixo do limiar de {str_limite}")
                else:
                    status = "[PASS]"
            elif "max" in regra:
                limite_max = regra["max"]
                str_limite = f"<= {limite_max:.1f}ms" if formato == "ms" else f"<= {limite_max}"
                if valor > limite_max:
                    status = "[REPROV]"
                    reprovado = True
                    falhas.append(
                        f"{nome}: obtido {str_valor} acima do limite máximo de {str_limite}"
                    )
                else:
                    status = "[PASS]"

        print(f"{nome:<40} | {str_valor:>10} | {str_limite:>15} | {status:^8}")

    print("-" * 80)

    if reprovado:
        print("\n[FALHA] Quality Gate NÃO APROVADO! Violações de limiar detectadas:")
        for falha in falhas:
            print(f"  ✖ {falha}")
        print("\nO pipeline de CI será interrompido para evitar regressão na main.")
        return False

    print("\n[SUCESSO] Todos os limiares de qualidade e fidelidade foram satisfeitos com sucesso!")
    print("O modelo cumpre 100% dos requisitos de governança e zero alucinação.\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Verificador de limites de regressão RAG (Quality Gate CI)."
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "data"
        / "benchmark"
        / "benchmark_results.json",
        help="Caminho do arquivo benchmark_results.json gerado pelo benchmark.",
    )
    args = parser.parse_args()

    aprovado = verificar_regressao(args.results, DEFAULT_THRESHOLDS)
    sys.exit(0 if aprovado else 1)


if __name__ == "__main__":
    main()
