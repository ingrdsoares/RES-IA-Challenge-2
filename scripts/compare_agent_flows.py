"""Compare recorded agent runs; quality labels come from explicit review, never HTTP status."""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def summary(data):
    return dict(
        Counter(c.get("operation", {}).get("status", "execution_error") for c in data["cases"])
    )


def evidence(case):
    legal = next((a for a in case.get("agents", []) if a["name"] == "legal"), None)
    sources = ((legal or {}).get("tool_result") or {}).get("sources", {})
    return len(sources), sum(len(s["text"]) for s in sources.values())


def response_text(case):
    if case.get("response"):
        return case["response"]["text"]
    return "Sem mensagem textual. Resultado estruturado: " + json.dumps(
        case.get("operation", {}).get("result", case.get("execution_error")), ensure_ascii=False
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", type=Path, default=Path("docs/avaliacao/2026-11-17-bateria-50-agentes.json")
    )
    parser.add_argument(
        "--current",
        type=Path,
        default=Path("docs/avaliacao/2026-11-17-bateria-50-agentes-40k.json"),
    )
    parser.add_argument(
        "--baseline-reviews",
        type=Path,
        default=Path("docs/avaliacao/2026-11-17-bateria-50-revisao.json"),
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=Path("docs/avaliacao/2026-11-17-bateria-50-revisao-40k.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/avaliacao/2026-11-17-comparacao-50-agentes-8k-40k.md"),
    )
    args = parser.parse_args()
    baseline = load(args.baseline)
    current = load(args.current)
    old = {c["id"]: c for c in baseline["cases"]}
    new = {c["id"]: c for c in current["cases"]}
    before = load(args.baseline_reviews)
    after = load(args.reviews) if args.reviews.exists() else {}
    for key, case in new.items():
        if key not in old or any(
            case[field] != old[key][field] for field in ("question", "expected", "profile")
        ):
            raise ValueError("Casos distintos não formam comparação pareada: " + key)
    lines = [
        "# Bateria de 50 perguntas — comparação 8K × 40K",
        "",
        f"Nova execução: **{len(new)}/50**. Nova revisão qualitativa: **{len(after)}/50**.",
        "",
        "## Método e limites",
        "",
        "- Mesmo roteiro, modelo Qwen3:8b, prompts, fontes indexadas, limiar 0,3 e até cinco trechos. Contas e empresas são fixtures fictícias novas para cada lote.",
        "- Lote anterior: janela de 8.192 tokens e corte fixo de 2.200 caracteres. Novo lote: janela de 40.960 tokens e orçamento dinâmico de evidências. As duas mudanças foram aplicadas juntas; este ensaio não isola apenas o tamanho da janela.",
        "- Catálogo com 4.026 documentos recebidos, mas somente três versões/348 trechos indexados para a recuperação. Vigência ignorada apenas no experimento. Não houve inclusão de novas fontes entre os lotes.",
        "- Execução automática por TestClient + executor real + Ollama/Qdrant/PostgreSQL. Sem testar transporte da fila RQ. Sem publicar regras fiscais reais.",
        "- Qualidade revisada pelo mesmo assistente com os critérios anteriores: adequada, parcial, incorreta e falha técnica. Não é revisão fiscal independente ou estimativa estatística de acurácia.",
        "- Cada pergunta inicia conversa nova. Pedidos de esclarecimento não são continuados com novas mensagens. Status succeeded não equivale a qualidade aprovada.",
        "",
        "Parâmetros efetivos do novo lote:",
        "",
        "```json",
        json.dumps(current["metadata"].get("parameters", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Resumo",
        "",
        f"Estados técnicos anteriores: `{summary(baseline)}`.",
        "",
        f"Estados técnicos novos: `{summary(current)}`.",
        "",
        "| Avaliação | 8K | 40K revisado |",
        "| --- | ---: | ---: |",
    ]
    old_counts = Counter(r["classification"] for r in before.values())
    new_counts = Counter(r["classification"] for r in after.values())
    for label in ("adequada", "parcial", "incorreta", "falha técnica"):
        lines.append(f"| {label} | {old_counts[label]} | {new_counts[label]} |")
    for title, data in [("8K", baseline), ("40K", current)]:
        times = [c["duration_seconds"] for c in data["cases"]]
        if times:
            lines += [
                "",
                f"{title}: mediana {statistics.median(times):.2f} s; máximo {max(times):.2f} s; total acumulado {sum(times):.2f} s.",
            ]
    findings = args.reviews.with_suffix(".md")
    if findings.exists():
        lines += ["", "## Diagnóstico da comparação", "", findings.read_text()]
    lines += [
        "",
        "## Casos pareados",
        "",
        "| Caso | 8K | 40K | Fontes/caracteres 8K → 40K |",
        "| --- | --- | --- | --- |",
    ]
    for key, c in old.items():
        n = new.get(key)
        left = evidence(c)
        right = evidence(n) if n else None
        lines.append(
            f"| {key} | {before[key]['classification']} | {after.get(key, {}).get('classification', 'pendente')} | {left} → {right or 'pendente'} |"
        )
    for key, c in old.items():
        n = new.get(key)
        review = after.get(key, {})
        lines += [
            "",
            f"### {key} — {c['category']}",
            "",
            f"**Pergunta:** {c['question']}",
            "",
            f"**Esperado:** {c['expected']}",
            "",
            "**Resposta 8K:**",
            "",
        ]
        lines += ["> " + line for line in response_text(c).splitlines()]
        lines += [
            "",
            f"**Avaliação 8K:** {before[key]['classification']}. {before[key]['reason']}",
            "",
            "**Resposta 40K:**",
            "",
        ]
        if not n:
            lines += ["Execução pendente."]
            continue
        lines += ["> " + line for line in response_text(n).splitlines()]
        lines += [
            "",
            f"**Avaliação 40K:** {review.get('classification', 'pendente')}. {review.get('reason', 'Revisão qualitativa pendente.')}",
            "",
            f"**Execução:** `{n.get('operation', {}).get('status', 'erro')}`; duração {n['duration_seconds']} s; tarefas criadas {n.get('tasks_created', 'não medido')}.",
            "",
            "**Agentes:** "
            + ", ".join(a["name"] + " (" + a["status"] + ")" for a in n.get("agents", []))
            + ".",
            "",
        ]
        for action in (n.get("response") or {}).get("actions", []):
            lines.append("- Ação: " + action["title"])
        for source in (n.get("response") or {}).get("citations", []):
            lines.append(
                f"- Fonte: [{source['title']}]({source['official_url']}); âncora `{source['anchor_id']}`; versão `{source['version_id']}`."
            )
        lines += [
            "",
            "<details><summary>Saídas estruturadas dos agentes — 40K</summary>",
            "",
            "```json",
            json.dumps(
                [
                    {
                        "name": a["name"],
                        "status": a["status"],
                        "result": a["result"],
                        "error": a["error"],
                    }
                    for a in n.get("agents", [])
                ],
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "</details>",
        ]
    lines += [
        "",
        "## Reprodução",
        "",
        "```bash",
        ".venv/bin/python scripts/evaluate_agent_flows.py --output docs/avaliacao/2026-11-17-bateria-50-agentes-40k.json",
        ".venv/bin/python scripts/compare_agent_flows.py",
        "```",
        "",
        "O runner grava cada caso e valida parâmetros/hash do dataset antes de retomar. Arquivo completo é retomado sem repetir os 50; para um novo experimento, escolha outro --output. A classificação qualitativa permanece separada da execução.",
    ]
    args.output.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
