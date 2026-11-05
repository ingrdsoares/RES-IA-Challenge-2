import csv
import json
from pathlib import Path

from evaluation.reports.excel import csv_safe, write_excel
from evaluation.reports.markdown import render
from evaluation.reports.plots import write_plots


def atomic_text(path, text):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_report(snapshot, summary, output_dir, comparison=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    from evaluation.dataset import canonical_hash

    identity = canonical_hash(
        {"snapshot": snapshot.model_dump(mode="json"), "summary": summary, "comparison": comparison}
    )
    marker = output_dir / "report_identity.json"
    if marker.exists() and json.loads(marker.read_text())["identity"] != identity:
        raise ValueError("Diretório já contém relatório de outra identidade")
    atomic_text(marker, json.dumps({"identity": identity}))
    rows = []
    sources = []
    for row in snapshot.results:
        flat = (
            row.case.model_dump()
            | row.attempt.model_dump()
            | {"judgment": row.judgment, "reviewer": row.reviewer, "rationale": row.rationale}
        )
        for metric in ["rouge_l", "bert_score"]:
            flat.update(
                {
                    f"{metric}_{key}": value
                    for key, value in getattr(row, metric).model_dump().items()
                }
            )
        rows.append(flat)
        sources.extend(
            {"case_id": row.case.id, "repeat_index": row.attempt.repeat_index, **source}
            for source in row.attempt.sources
        )
    atomic_text(
        output_dir / "results.json",
        json.dumps(
            [r.model_dump(mode="json") for r in snapshot.results],
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
    )
    summary = summary | {
        "metric_fingerprint": snapshot.metric_fingerprint,
        "metric_metadata": snapshot.metric_metadata,
    }
    atomic_text(
        output_dir / "summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False),
    )
    headers = list(dict.fromkeys(key for row in rows for key in row)) or ["case_id"]
    with (output_dir / "results.csv.tmp").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, headers)
        writer.writeheader()
        writer.writerows({k: csv_safe(v) for k, v in row.items()} for row in rows)
    (output_dir / "results.csv.tmp").replace(output_dir / "results.csv")

    def distribution_rows(groups):
        result = []
        for scope, group in groups.items():
            for metric, stats in group["metrics"].items():
                row = {
                    "scope": scope,
                    "metric": metric,
                    **{
                        k: v
                        for k, v in stats.items()
                        if k not in ["percentiles", "ci95", "sample_size"]
                    },
                }
                row.update(stats.get("percentiles") or {})
                row.update(
                    ci95_lower=stats["ci95"][0] if stats.get("ci95") else None,
                    ci95_upper=stats["ci95"][1] if stats.get("ci95") else None,
                )
                result.append(row)
        return result

    tables = {
        "Resultados": rows,
        "Resumo": distribution_rows({scope: summary[scope] for scope in ["all", "primary"]}),
        "Categorias": distribution_rows(summary["categories"]),
        "Falhas": [
            r
            for r in rows
            if r["state"] != "success"
            or r["rouge_l_state"] != "success"
            or r["bert_score_state"] != "success"
        ],
        "Configuração": [
            {"name": "manifest", "value": snapshot.manifest.model_dump(mode="json")},
            {"name": "metrics", "value": snapshot.metric_metadata},
            {"name": "statistics", "value": summary["config"]},
            {
                "name": "presentation_policy",
                "value": (
                    "CSV prefixes potentially executable strings; Excel stores te"
                    "xt explicitly; controls JSON-encoded in Textos; originals pr"
                    "eserved in results.json"
                ),
            },
        ],
        "Abstenções": [
            r
            for r in rows
            if r["expected_behavior"] != "answer" or r["rag_status"] == "insufficient_context"
        ],
        "Variabilidade": summary["all"]["variability"],
        "Tamanho amostral": [
            {"metric": k, **v["sample_size"]} for k, v in summary["primary"]["metrics"].items()
        ],
        "Fontes": sources,
    }
    if comparison:
        tables["Comparação"] = [{"metric": k, **v} for k, v in comparison["metrics"].items()]
        atomic_text(
            output_dir / "comparison.json", json.dumps(comparison, ensure_ascii=False, indent=2)
        )
    images = write_plots(snapshot, summary, output_dir)
    write_excel(output_dir / "report.xlsx.tmp", tables, images)
    (output_dir / "report.xlsx.tmp").replace(output_dir / "report.xlsx")
    atomic_text(output_dir / "report.md", render(snapshot, summary, comparison, images))
    return list(output_dir.iterdir())


def write_template(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any((output_dir / name).exists() for name in ["dataset.xlsx", "report.xlsx", "report.md"]):
        raise ValueError("Template já existe; use outro diretório para preservar os arquivos")
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Dataset"
    ws.append(
        [
            "id",
            "category",
            "question",
            "ground_truth",
            "expected_behavior",
            "split",
            "group_id",
            "expected_sources",
            "metadata",
        ]
    )
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    instructions = wb.create_sheet("Instruções")
    instructions.append(
        [
            (
                "Dataset ainda não fornecido. Preencha somente com perguntas "
                "reais e referências revisadas."
            )
        ]
    )
    instructions.append(
        [
            (
                "Exporte para JSON ou JSONL antes de executar validate; não u"
                "sar resultados do próprio RAG como referência sem revisão in"
                "dependente."
            )
        ]
    )
    wb.save(output_dir / "dataset.xlsx")
    write_excel(
        output_dir / "report.xlsx",
        {
            name: []
            for name in [
                "Resultados",
                "Resumo",
                "Categorias",
                "Falhas",
                "Configuração",
                "Abstenções",
                "Variabilidade",
                "Tamanho amostral",
                "Fontes",
            ]
        },
    )
    atomic_text(
        output_dir / "report.md",
        (
            "# Modelo de relatório\n\nDataset ainda não fornecido. Nenhuma "
            "pergunta foi executada e nenhuma pontuação foi medida.\n"
        ),
    )
    return list(output_dir.iterdir())
