from collections import defaultdict

import numpy as np

from evaluation.metrics.fidelidade import get_score
from evaluation.statistics import METRICAS, summarize_values


def compare_runs(a, b, config):
    ca = {c.id: c.model_dump() for c in a.manifest.selection.cases}
    cb = {c.id: c.model_dump() for c in b.manifest.selection.cases}
    if ca != cb or a.manifest.run_config.repeats != b.manifest.run_config.repeats:
        raise ValueError("Comparação exige mesmos casos, referências e repetições")
    if a.metric_fingerprint != b.metric_fingerprint:
        raise ValueError("Configurações de métricas incompatíveis")
    for snapshot in [a, b]:
        if any(r.case.model_dump() != ca[r.case.id] for r in snapshot.results):
            raise ValueError("Casos pontuados divergem do manifest")
    lookup = {(r.case.id, r.attempt.repeat_index): r for r in b.results}

    def calculate(rows, metric):
        if metric == "bert_score" and (
            not a.metric_metadata.get("resolved") or not b.metric_metadata.get("resolved")
        ):
            return {"error": "unresolved_model_configuration"}
        by_id = defaultdict(list)
        excluded = []
        for left in rows:
            key = (left.case.id, left.attempt.repeat_index)
            right = lookup.get(key)
            ls = get_score(left, metric)
            rs = get_score(right, metric) if right else None
            if ls.state != "success" or rs is None or rs.state != "success":
                excluded.append(list(key))
                continue
            by_id[key[0]].append((ls.f1, rs.f1))
        differences = {
            key: float(np.mean([right - left for left, right in values]))
            for key, values in by_id.items()
        }
        summary = summarize_values(list(differences.values()), config)
        summary.update(
            differences=differences,
            excluded_pairs=excluded,
            a_wins=sum(v < -1e-12 for v in differences.values()),
            b_wins=sum(v > 1e-12 for v in differences.values()),
            ties=sum(abs(v) <= 1e-12 for v in differences.values()),
        )
        return summary

    result = {
        "run_a": a.manifest.run_id,
        "run_b": b.manifest.run_id,
        "direction": "B - A",
        "metrics": {},
        "categories": {},
        "behaviors": {},
    }
    for metric in METRICAS:
        if metric == "bert_score" and not a.metric_metadata.get("resolved"):
            result["metrics"][metric] = {"error": "unresolved_model_configuration"}
        else:
            result["metrics"][metric] = calculate(a.results, metric)
    for category in sorted({r.case.category for r in a.results}):
        result["categories"][category] = {
            m: calculate([r for r in a.results if r.case.category == category], m) for m in METRICAS
        }
    for behavior in ["answer", "abstain", "clarify"]:
        result["behaviors"][behavior] = {
            m: calculate([r for r in a.results if r.case.expected_behavior == behavior], m)
            for m in METRICAS
        }
    return result


def apply_adjudications(snapshot, entries):
    result = snapshot.model_copy(deep=True)
    rows = {(r.case.id, r.attempt.repeat_index): r for r in result.results}
    seen = set()
    for entry in entries:
        key = (entry["case_id"], entry["repeat_index"])
        if entry["run_id"] != result.manifest.run_id or key not in rows or key in seen:
            raise ValueError("Adjudicação duplicada ou de execução/caso inexistente")
        seen.add(key)
        judgment = entry.get("judgment", "not_assessed")
        if judgment not in ["correct", "incorrect", "not_assessed"]:
            raise ValueError("Julgamento inválido")
        if judgment != "not_assessed" and (
            not entry.get("reviewer", "").strip() or not entry.get("rationale", "").strip()
        ):
            raise ValueError("Revisão exige revisor e justificativa")
        rows[key].judgment = judgment
        rows[key].reviewer = entry.get("reviewer")
        rows[key].rationale = entry.get("rationale")
    return result
