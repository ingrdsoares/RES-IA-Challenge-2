import json

import pytest
from evaluation.cli import main
from evaluation.comparison import apply_adjudications, compare_runs
from evaluation.dataset import select_cases
from evaluation.schemas import EvalCase, MetricScore, SelectionConfig, StatsConfig
from evaluation.statistics import summarize_run
from evaluation.storage import RunStore


class Client:
    calls = 0

    def metadata(self):
        return {"mode": "software-test-only"}

    def query(self, question):
        from app.schemas import QueryResponse

        type(self).calls += 1
        return QueryResponse(status="answered", answer="Texto de referência", sources=[])

    def close(self):
        pass


class Bert:
    def __init__(self, config, references):
        pass

    def metadata(self):
        return {
            "resolved": True,
            "revision": "controlled-test",
            "configuration": "test-double-not-real-BERT",
        }

    def score_pairs(self, pairs):
        return [MetricScore(state="success", precision=0.8, recall=0.8, f1=0.8) for p in pairs]


def run_fixture(tmp_path, capsys):
    dataset = tmp_path / "fixture.json"
    dataset.write_text(
        json.dumps(
            [
                dict(
                    id=str(i),
                    category="software-test",
                    question=f"Fixture {i}",
                    ground_truth="Texto de referência",
                )
                for i in range(2)
            ]
        )
    )
    run = tmp_path / "run"
    args = [
        "run",
        "--dataset",
        str(dataset),
        "--run-dir",
        str(run),
        "--limit",
        "2",
        "--rag-version",
        "fixture",
        "--corpus-version",
        "fixture",
        "--bootstrap",
        "100",
    ]
    assert main(args, Client, Bert) == 0
    assert main(args + ["--resume"], Client, Bert) == 0
    with RunStore(run) as store:
        snap = store.snapshot()
    return run, snap


def test_full_workflow_and_resume(tmp_path, capsys):
    Client.calls = 0
    run, snap = run_fixture(tmp_path, capsys)
    assert Client.calls == 2
    assert len(list(run.glob("reports/*/*/report.xlsx"))) == 1
    assert all(r.rouge_l.f1 == 1 and r.bert_score.f1 == 0.8 for r in snap.results)
    assert (
        main(
            ["report", "--run-dir", str(run), "--bootstrap", "100"],
            lambda: pytest.fail("report must not create RAG"),
        )
        == 0
    )


def test_paired_bootstrap_and_repetitions(tmp_path, capsys):
    _, a = run_fixture(tmp_path, capsys)
    b = a.model_copy(deep=True)
    for r in b.results:
        r.rouge_l.f1 = 0.9
    compared = compare_runs(a, b, StatsConfig(bootstrap=100))
    assert compared["metrics"]["rouge_l"]["mean"] == pytest.approx(-0.1)
    assert compared["metrics"]["rouge_l"]["a_wins"] == 2
    assert apply_adjudications(a, []).results[0].judgment == "not_assessed"
    with pytest.raises(ValueError):
        apply_adjudications(
            a,
            [
                {
                    "run_id": a.manifest.run_id,
                    "case_id": "0",
                    "repeat_index": 1,
                    "judgment": "correct",
                }
            ],
        )
    row = a.results[0].model_copy(deep=True)
    row.attempt.repeat_index = 2
    row.rouge_l.f1 = 0
    a.results.append(row)
    assert (
        summarize_run(a.manifest, a.results, StatsConfig(bootstrap=100))["primary"]["metrics"][
            "rouge_l"
        ]["mean"]
        == 0.75
    )


def test_selection_scales_without_duplicate_questions():
    cases = [
        EvalCase(id=f"{i:03}", category="fixture", question=f"Q{i}", ground_truth="R")
        for i in range(250)
    ]
    a = select_cases(cases, SelectionConfig(preset="reference"))
    b = select_cases(list(reversed(cases)), SelectionConfig(preset="reference"))
    assert len(a.cases) == 200 and a.selection_hash == b.selection_hash
    assert len(select_cases(cases, SelectionConfig(all_cases=True)).cases) == 250
    with pytest.raises(ValueError):
        select_cases(cases[:29], SelectionConfig())


def test_scores_do_not_survive_changed_attempt(tmp_path, capsys):
    run, snapshot = run_fixture(tmp_path, capsys)
    with RunStore(run) as store:
        attempt = store.attempts()[0]
        attempt.answer = "Resposta alterada"
        store.finish(attempt)
        assert len(store.read_metrics(snapshot.metric_fingerprint)) == 1
        with pytest.raises(ValueError):
            store.snapshot()


def test_export_rejects_different_identity(tmp_path):
    from evaluation.reports.export import write_report
    from evaluation.statistics import summarize_run

    run, snap = run_fixture(tmp_path, __import__("types").SimpleNamespace())
    out = tmp_path / "export"
    summary = summarize_run(snap.manifest, snap.results, StatsConfig(bootstrap=100))
    write_report(snap, summary, out)
    snap.manifest.run_id = "other-run"
    with pytest.raises(ValueError):
        write_report(snap, summary, out)


def test_unresolved_bert_is_not_compared_in_categories(tmp_path, capsys):
    _, a = run_fixture(tmp_path, capsys)
    a.metric_metadata["resolved"] = False
    result = compare_runs(a, a, StatsConfig(bootstrap=100))
    assert "error" in result["categories"]["software-test"]["bert_score"]


def test_category_available_counts_are_local(tmp_path, capsys):
    _, snap = run_fixture(tmp_path, capsys)
    snap.manifest.selection.available = {"answer": 200}
    summary = summarize_run(snap.manifest, snap.results, StatsConfig())
    assert (
        summary["categories"]["software-test"]["metrics"]["rouge_l"]["sample_size"]["available"]
        == 2
    )
