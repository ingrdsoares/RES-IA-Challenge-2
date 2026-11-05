import json
from openpyxl import load_workbook
from evaluation.reports.export import write_template, write_report
from evaluation.schemas import EvaluationSnapshot, ScoredAttempt, AttemptResult, MetricScore
from evaluation.storage import make_manifest
from evaluation.dataset import select_cases
from evaluation.schemas import EvalCase, RunConfig, SelectionConfig, StatsConfig
from evaluation.statistics import summarize_run
from evaluation.comparison import compare_runs


def snapshot():
    case=EvalCase(id='fixture',category='test-only',question='Fixture de software',ground_truth='Referência de teste')
    config=RunConfig(selection=SelectionConfig(limit=1),rag_version='test-only',corpus_version='test-only')
    manifest=make_manifest(select_cases([case],config.selection),config,{})
    row=ScoredAttempt(case=case,attempt=AttemptResult(case_id=case.id,repeat_index=1,state='success',rag_status='answered',answer='='+'x'*40000),rouge_l=MetricScore(state='success',precision=.5,recall=.5,f1=.5))
    return EvaluationSnapshot(manifest=manifest,metric_fingerprint='fixture-only',metric_metadata={'resolved':False},results=[row])


def test_excel_safe_complete_text(tmp_path):
    s=snapshot()
    write_report(s,summarize_run(s.manifest,s.results,StatsConfig()),tmp_path)
    wb=load_workbook(tmp_path/'report.xlsx')
    assert 'Textos' in wb.sheetnames
    assert all(cell.data_type!='f' for sheet in wb for row in sheet for cell in row)
    texts=[row for row in wb['Textos'].iter_rows(min_row=2,values_only=True) if row[1]=='answer' and row[0].startswith('Resultados:')]
    assert ''.join(r[3] for r in texts)==s.results[0].attempt.answer
    assert json.loads((tmp_path/'results.json').read_text())[0]['attempt']['answer']==s.results[0].attempt.answer


def test_template_has_no_invented_cases(tmp_path):
    write_template(tmp_path)
    assert load_workbook(tmp_path/'dataset.xlsx')['Dataset'].max_row==1


def test_pairing_rejects_different_reference():
    a=snapshot(); b=snapshot()
    b.results[0].case.ground_truth='Alterado'
    with __import__('pytest').raises(ValueError):
        compare_runs(a,b,StatsConfig())


def test_template_does_not_overwrite_user_data(tmp_path):
    write_template(tmp_path)
    (tmp_path/'dataset.xlsx').write_bytes(b'user data')
    with __import__('pytest').raises(ValueError): write_template(tmp_path)
    assert (tmp_path/'dataset.xlsx').read_bytes()==b'user data'


def test_summary_excel_has_numeric_metric_columns(tmp_path):
    s=snapshot()
    write_report(s,summarize_run(s.manifest,s.results,StatsConfig()),tmp_path)
    wb=load_workbook(tmp_path/'report.xlsx')
    rows=list(wb['Resumo'].iter_rows(values_only=True))
    assert 'mean' in rows[0]
    assert isinstance(rows[1][rows[0].index('mean')],float)
