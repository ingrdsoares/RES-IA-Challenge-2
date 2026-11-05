from datetime import datetime, timezone
from time import perf_counter


def collect_run(client, store, retry_failed=False, retry_uncertain=False):
    store.mark_interrupted()
    cases = {c.id:c for c in store.manifest().selection.cases}
    called = 0
    for previous in store.attempts():
        eligible = previous.state=='planned' or (previous.state=='error' and retry_failed) or (previous.state=='uncertain' and retry_uncertain)
        if not eligible:
            continue
        result = store.start(previous.case_id, previous.repeat_index)
        result.started_at = datetime.now(timezone.utc).isoformat()
        started = perf_counter()
        called += 1
        try:
            response = client.query(cases[result.case_id].question)
            result.rag_status = response.status
            result.answer = response.answer
            result.sources = [s.model_dump(mode='json') for s in response.sources]
            result.state = 'success' if response.answer.strip() else 'error'
            if result.state=='error':
                result.error_type = 'EmptyAnswer'
        except Exception as exc:
            result.state = 'error'
            result.error_type = type(exc).__name__
            result.error_message = 'Consulta não concluída; detalhes internos omitidos.'
        result.duration_seconds = perf_counter()-started
        result.ended_at = datetime.now(timezone.utc).isoformat()
        store.finish(result)
    return {'calls':called, 'states':{s:sum(a.state==s for a in store.attempts()) for s in ['planned','success','error','uncertain']}}
