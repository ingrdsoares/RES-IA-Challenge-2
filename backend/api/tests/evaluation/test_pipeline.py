from pathlib import Path
import pytest
from evaluation.schemas import EvalCase, SelectionConfig, RunConfig, StatsConfig, MetricConfig
from evaluation.dataset import select_cases
from evaluation.storage import RunStore, make_manifest
from evaluation.collect import collect_run
from evaluation.statistics import summarize_values, estimate_sample_size
from evaluation.metrics.rouge import RougeMetric


def test_statistics():
    result = summarize_values([.2, .4, .6], StatsConfig())
    assert result['mean'] == pytest.approx(.4)
    assert result['sample_std'] == pytest.approx(.2)
    assert summarize_values([.4], StatsConfig())['ci95'] is None
    assert estimate_sample_size(.2, .05, 30)['required'] == 62


def test_portuguese_rouge():
    score = RougeMetric().score('ação fiscal', 'ação')
    assert score.f1 == pytest.approx(2/3)
    assert score.precision == 1


def test_resume_and_failure(tmp_path):
    cases = [EvalCase(id=str(i), category='fixture', question=f'Q{i}', ground_truth='Resposta') for i in range(2)]
    selection = select_cases(cases, SelectionConfig(all_cases=True))
    config = RunConfig(selection=SelectionConfig(all_cases=True), rag_version='fixture', corpus_version='fixture')
    manifest = make_manifest(selection, config, {})
    class Client:
        calls = 0
        def query(self, question):
            self.calls += 1
            if question == 'Q0':
                raise TimeoutError()
            from app.schemas import QueryResponse
            return QueryResponse(status='answered', answer='Resposta', sources=[])
    client = Client()
    with RunStore(tmp_path) as store:
        store.initialize(manifest)
        collect_run(client, store)
        collect_run(client, store)
        assert client.calls == 2
        assert {r.state for r in store.attempts()} == {'success', 'error'}
        store.start('0', 1)
        store.mark_interrupted()
        collect_run(client, store)
        assert client.calls == 2
        assert next(r for r in store.attempts() if r.case_id == '0').state == 'uncertain'


def test_initialization_is_atomic(tmp_path):
    cases=[EvalCase(id=str(i),category='fixture',question=f'Q{i}',ground_truth='R') for i in range(2)]
    config=RunConfig(selection=SelectionConfig(all_cases=True),rag_version='fixture',corpus_version='fixture')
    manifest=make_manifest(select_cases(cases,config.selection),config,{})
    last=manifest.selection.cases[-1].id
    with RunStore(tmp_path) as store:
        store.db.execute(f"CREATE TRIGGER reject_row BEFORE INSERT ON attempts WHEN NEW.case_id='{last}' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with pytest.raises(Exception): store.initialize(manifest)
        assert store.db.execute('SELECT COUNT(*) FROM manifest').fetchone()[0]==0
        assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==0
