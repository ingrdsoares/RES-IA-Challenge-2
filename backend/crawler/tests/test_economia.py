from datetime import date
import json
import pytest
import httpx

from backend.crawler.economia import SOURCES, parse_series, ingest, collect

START=date(2025,1,1)
END=date(2026,11,3)


def test_preserves_decimal_precision_negative_values_and_dates():
    raw=json.dumps([{'data':'01/02/2025','valor':'-0.0200'},{'data':'01/01/2025','valor':'0.1600'}]).encode()
    records=parse_series('ipca',raw,START,END)
    assert records[0]=={'data':'2025-01-01','data_original':'01/01/2025','valor':'0.1600'}
    assert records[1]['valor']=='-0.0200'


@pytest.mark.parametrize('data',[
    [],{},[{'data':'31/02/2025','valor':'1'}],[{'data':'01/01/2025','valor':'NaN'}],
    [{'data':'01/01/2025','valor':1.2}],[{'data':'01/01/2025','valor':'1,25'}],
    [{'data':'01/01/2024','valor':'1'}],
    [{'data':'01/01/2025','valor':'1'},{'data':'01/01/2025','valor':'2'}]])
def test_rejects_invalid_or_duplicate_observations(data):
    with pytest.raises(ValueError):parse_series('selic-meta',json.dumps(data).encode(),START,END)


def test_monthly_series_rejects_two_observations_in_same_month():
    raw=json.dumps([{'data':'01/01/2025','valor':'1'},{'data':'15/01/2025','valor':'2'}]).encode()
    with pytest.raises(ValueError):parse_series('ipca',raw,START,END)


def test_snapshot_keeps_original_units_and_query_window(tmp_path):
    raw=b'[{"data":"01/01/2025","valor":"12.2500"}]'
    path=ingest('selic-meta',raw,tmp_path,START,END)
    assert (path.parent/'original.json').read_bytes()==raw
    meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
    assert meta['codigo_sgs']==432 and meta['unidade']=='percentual ao ano'
    assert meta['inicio_solicitado']=='2025-01-01' and meta['fim_solicitado']=='2026-11-03'
    assert '12.2500' in path.read_text(encoding='utf-8')
    before=path.read_bytes()
    assert ingest('selic-meta',raw,tmp_path,START,END)==path
    assert path.read_bytes()==before
    assert ingest('selic-meta',raw,tmp_path,START,date(2026,10,1))!=path


def test_http_failure_does_not_stop_other_series(tmp_path):
    def respond(request):
        assert request.url.params['dataInicial']=='01/01/2025'
        assert request.url.params['dataFinal']=='03/11/2026'
        return httpx.Response(503) if '.432/' in str(request.url) else httpx.Response(200,json=[{'data':'01/01/2025','valor':'0.16'}])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report=collect(list(SOURCES),tmp_path,client,START,END)
    assert [s['status'] for s in report['series']]==['erro','extraido']
    assert (tmp_path/'indice.md').exists()
