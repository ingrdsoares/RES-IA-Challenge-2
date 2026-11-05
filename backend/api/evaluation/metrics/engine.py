import json
from time import perf_counter
from evaluation.dataset import canonical_hash
from evaluation.schemas import ScoredAttempt, MetricScore
from evaluation.metrics.rouge import RougeMetric
from evaluation.metrics.bert import BertMetric, package_versions


def score_run(store, config, bert_factory=BertMetric):
    manifest=store.manifest()
    cases={c.id:c for c in manifest.selection.cases}
    attempts=store.attempts()
    references=[c.ground_truth for c in manifest.selection.cases]
    started=perf_counter()
    try:
        bert=bert_factory(config,references)
        metadata=bert.metadata()
        init_error=None
    except Exception as exc:
        bert=None
        init_error=type(exc).__name__
        metadata={'resolved':False,'error':init_error,'requested_config':config.model_dump(exclude={'allow_download'}),'versions':package_versions()}
    metadata['idf_corpus_hash']=canonical_hash(references) if config.idf else None
    fingerprint=canonical_hash({k:v for k,v in metadata.items() if k not in ['path','native_hash']})
    with store.db:
        store.db.execute('INSERT OR REPLACE INTO metric_config VALUES (?,?)',(fingerprint,json.dumps(metadata)))
    cached={(r.attempt.case_id,r.attempt.repeat_index,r.attempt.attempt_revision):r for r in store.read_metrics(fingerprint)}
    rouge=RougeMetric()
    pending=[]
    for attempt in attempts:
        key=(attempt.case_id,attempt.repeat_index,attempt.attempt_revision)
        if key in cached:
            continue
        result=ScoredAttempt(attempt=attempt,case=cases[attempt.case_id])
        if attempt.state!='success' or not attempt.answer or not attempt.answer.strip() or attempt.rag_status=='empty_knowledge_base':
            result.rouge_l=MetricScore(error='ineligible_response')
            result.bert_score=MetricScore(error='ineligible_response')
            store.save_metric(fingerprint,result)
            continue
        try:
            result.rouge_l=rouge.score(result.case.ground_truth,attempt.answer)
        except Exception as exc:
            result.rouge_l=MetricScore(state='error',error=type(exc).__name__)
        if bert is None:
            result.bert_score=MetricScore(state='error',error=init_error)
            store.save_metric(fingerprint,result)
        else:
            pending.append(result)
    if bert and pending:
        scores=bert.score_pairs([(r.case.ground_truth,r.attempt.answer) for r in pending])
        for result,score in zip(pending,scores,strict=True):
            result.bert_score=score
            store.save_metric(fingerprint,result)
    return {'metric_fingerprint':fingerprint,'elapsed_seconds':perf_counter()-started,'bert_initialization_error':init_error}
