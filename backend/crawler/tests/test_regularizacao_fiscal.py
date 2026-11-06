import hashlib,json
import httpx
from backend.crawler import regularizacao_fiscal as c

INFO={'title':'Parcelamento MEI','url':'https://www.gov.br/teste','identity':['parcelamento','MEI'],'format':'html'}
RAW=b'<h1>Parcelamento MEI</h1><div id="content-core"><p>Orientacoes publicas MEI e parcelamento.</p><a href="/login">Acesso ao servico</a></div>'

def test_collect_preserves_source_and_reuses_version(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'SOURCES',{'teste':INFO})
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=RAW))) as client:
        first=c.collect(['teste'],tmp_path,client);second=c.collect(['teste'],tmp_path,client)
    assert first['documentos'][0]['sha256']==hashlib.sha256(RAW).hexdigest()
    assert first['documentos'][0]['markdown']==second['documentos'][0]['markdown']
    assert len(list(tmp_path.glob('teste/*/original.html')))==1
    assert 'orientacoes_publicas_sem_consulta_individual' in first['escopo']
    assert 'teste' in (tmp_path/'indice.md').read_text(encoding='utf-8')

def test_rejects_unrelated_page_and_reports_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'SOURCES',{'teste':INFO})
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'<h1>Erro</h1><div id="content-core">Indisponivel</div>'))) as client:
        report=c.collect(['teste'],tmp_path,client)
    assert report['status']=='parcial' and report['documentos'][0]['status']=='erro'
    assert not list(tmp_path.glob('teste/*/original.html'))

def test_http_error_is_not_published_as_document(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'SOURCES',{'teste':INFO})
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(404))) as client:
        report=c.collect(['teste'],tmp_path,client)
    assert report['status']=='parcial'
    assert not list(tmp_path.glob('teste/*/original.html'))

def test_explicit_editorial_container_is_supported(tmp_path,monkeypatch):
    info={**INFO,'content_selector':'#content'}
    monkeypatch.setattr(c,'SOURCES',{'teste':info})
    raw=b'<h1>Parcelamento MEI</h1><div id="content"><p>Parcelamento MEI: orientacoes.</p><nav>Menu alheio</nav></div>'
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw))) as client:
        report=c.collect(['teste'],tmp_path,client)
    assert report['status']=='coleta_concluida'
    text=(tmp_path/report['documentos'][0]['markdown']).read_text(encoding='utf-8')
    assert 'orientacoes' in text and 'Menu alheio' not in text
