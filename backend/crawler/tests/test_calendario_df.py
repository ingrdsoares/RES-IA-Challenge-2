import hashlib
import json

import httpx
import pytest
from backend.crawler import calendario_df as m


def test_published_months_never_synthesizes_urls():
    raw=b'<h1>2026</h1><div id="content-core"><a href="2026/Janeiro">Jan</a><a href="https://evil.test/2026/Dezembro">Dez</a></div>'
    assert m.published_months(raw)=={'2026-01':m.obrigacoes.BASE+'/2026/Janeiro'}


def test_literal_dates_categories_nested_sinj_and_struck_history():
    raw='''<body><div id="div_texto"><p linkname="art1">Calendário feriados<p linkname="I">I - 4 de junho: Corpus Christi (feriado local);<p linkname="II"><s>28 de outubro: ponto facultativo</s><p linkname="III">28 de outubro: a ser comemorado no dia 30 de outubro de 2026 (ponto facultativo);<p linkname="IV">24 de dezembro: ponto facultativo após as 14 horas</div></body>'''.encode()
    rows=m.calendar_rows(raw,'df',{'url':'https://official.test','esfera':'DF','content_selector':'#div_texto'})
    assert [(r['data'],r['categoria']) for r in rows]==[('2026-06-04','feriado'),('2026-10-30','ponto_facultativo'),('2026-12-24','horario_reduzido')]
    assert rows[0]['unidade']=='I'
    assert all(r['deslocamento_vencimento_fiscal']=='nao_inferido' for r in rows)


def test_impossible_literal_date_is_rejected():
    with pytest.raises(ValueError,match='Data impossível'):
        m.calendar_rows('<p>31 de fevereiro: feriado</p>'.encode(),'x',{'url':'x','esfera':'DF'})


def test_cached_client_avoids_duplicate_downloads():
    calls=[]
    def respond(request): calls.append(str(request.url));return httpx.Response(200,content=b'original')
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        cached=m.CachedClient(client,{})
        assert cached.get('https://official.test').content==cached.get('https://official.test').content
    assert len(calls)==1


def test_manifest_reuse_checks_original_hash(tmp_path):
    path=m.ingest('source',{'url':'https://official.test','title':'Test','identity':['test']},b'<h1>Test</h1><div id="content-core">Test text</div>',tmp_path)
    folder=path.parent
    meta=json.loads((folder/'metadados.json').read_text(encoding='utf8'))
    report={'fontes':[{**meta,'markdown':path.relative_to(tmp_path).as_posix()}]}
    (tmp_path/'manifesto.json').write_text(json.dumps(report))
    (tmp_path/'referencias.json').write_text('[]')
    (tmp_path/'indice.md').write_text('# Test')
    assert m.validated_manifest(tmp_path)==report
    path.write_text('corrupt')
    assert m.validated_manifest(tmp_path) is None
    assert path.read_text(encoding='utf8').endswith('Test text\n')
    (folder/'original.html').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='corrompido'):m.validated_manifest(tmp_path)


def test_access_failure_is_error_not_missing_publication(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'SOURCES',{})
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(503))) as client:
        report=m.collect(tmp_path,client,existing=tmp_path/'empty')
    assert report['fontes'][0]['status']=='erro'
    assert report['meses']==[]


def test_absent_months_record_index_observation(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'SOURCES',{})
    raw=b'<h1>2026</h1><div id="content-core">Agenda 2026, sem links mensais</div>'
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw))) as client:
        report=m.collect(tmp_path,client,existing=tmp_path/'empty')
    assert len(report['meses'])==12
    assert all(x['status']=='nao_encontrado_no_indice' for x in report['meses'])


def test_failure_one_month_keeps_next_month(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'SOURCES',{})
    raw=b'<h1>2026</h1><div id="content-core"><a href="2026/Janeiro">Jan</a><a href="2026/Fevereiro">Fev</a></div>'
    calls=[]
    def monthly(period,output,client):
        calls.append(period)
        if period=='2026-01': raise ValueError('broken January')
        return {'fontes':[], 'referencias_por_palavra_chave':0}
    monkeypatch.setattr(m.obrigacoes,'collect',monthly)
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw))) as client:
        report=m.collect(tmp_path,client,existing=tmp_path/'empty')
    assert calls==['2026-01','2026-02']
    assert report['meses'][0]['status']=='erro'
    assert report['meses'][1]['status']=='extraido'


def test_missing_or_corrupt_references_force_regeneration(tmp_path):
    (tmp_path/'manifesto.json').write_text(json.dumps({'fontes':[]}))
    (tmp_path/'indice.md').write_text('# Test')
    assert m.validated_manifest(tmp_path) is None
    (tmp_path/'referencias.json').write_text('[]')
    assert m.validated_manifest(tmp_path)=={'fontes':[]}
    (tmp_path/'referencias.json').write_text('[{"inventado":true}]')
    assert m.validated_manifest(tmp_path) is None


def test_norm_citation_date_is_not_a_calendar_day():
    raw='<p>A alteração foi estabelecida pela Portaria MGI nº 8.821, de 26 de outubro de 2026, que modificou o calendário de feriados e pontos facultativos.</p>'.encode()
    assert m.calendar_rows(raw,'inpi',{'url':'https://official.test','esfera':'federal'})==[]


def test_ordinal_day_survives_unicode_normalization():
    rows=m.calendar_rows('<p>I - 1º de janeiro: feriado nacional</p>'.encode(),'x',{'url':'x','esfera':'DF'})
    assert rows[0]['data']=='2026-01-01'


def test_normative_layers_and_correction_preserve_original(tmp_path):
    assert all(info['camada']==('A' if any(part in key for part in ('-lei-','-decreto-','-portaria-')) else 'B') for key,info in m.SOURCES.items())
    path=m.ingest('agenda-indice-2026',{'url':'https://official.test','title':'Test','identity':['test']},b'<h1>Test</h1><div id="content-core">Test</div>',tmp_path)
    before=json.loads((path.parent/'metadados.json').read_text(encoding='utf8'))
    original=(path.parent/'original.html').read_bytes()
    m.correct_existing_layers(tmp_path)
    after=json.loads((path.parent/'metadados.json').read_text(encoding='utf8'))
    assert after['camada']=='A' and '\ncamada: A\n' in path.read_text(encoding='utf8')
    assert after['coletado_em']==before['coletado_em']
    assert after['source_url']==before['source_url']
    assert after['sha256']==before['sha256']==hashlib.sha256(original).hexdigest()
    assert (path.parent/'original.html').read_bytes()==original
