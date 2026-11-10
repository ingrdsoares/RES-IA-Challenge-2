import hashlib
import json
from pathlib import Path

import httpx
import pytest

from backend.crawler.manuais import SOURCES, collect, ingest


@pytest.fixture
def source(monkeypatch):
    entry = {'title': 'Documento oficial de teste', 'url': 'https://example.test/manual.pdf',
             'identity': ['ANEXO I'], 'kind': 'manual'}
    monkeypatch.setitem(SOURCES, 'teste', entry)
    return 'teste'


@pytest.fixture
def raw_pdf():
    return (Path(__file__).parent/'fixtures/cgsn140-anexo-i.pdf').read_bytes()


def test_manual_snapshot_preserves_pdf_and_official_guidance_metadata(source, raw_pdf, tmp_path):
    path = ingest(source,raw_pdf,tmp_path)
    meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
    assert meta['camada']=='B'
    assert meta['sha256']==hashlib.sha256(raw_pdf).hexdigest()
    assert meta['source_url']==SOURCES[source]['url']
    assert meta['paginas']==1 and meta['tabelas']==2
    assert meta['vigencia']=='nao_verificada'
    assert (path.parent/'original.pdf').read_bytes()==raw_pdf
    md=path.read_text(encoding='utf-8')
    assert '## Página 1' in md and '4,00%' in md
    before=path.read_bytes()
    assert ingest(source,raw_pdf,tmp_path)==path
    assert path.read_bytes()==before


def test_identity_mismatch_is_rejected_before_writing(source,raw_pdf,tmp_path,monkeypatch):
    monkeypatch.setitem(SOURCES[source],'identity',['MANUAL INEXISTENTE'])
    with pytest.raises(ValueError,match='identidade'):
        ingest(source,raw_pdf,tmp_path)
    assert list(tmp_path.iterdir())==[]


def test_html_error_is_not_published_as_pdf(source,tmp_path):
    with pytest.raises(ValueError):
        ingest(source,b'<html>Acesso negado</html>',tmp_path)
    assert list(tmp_path.iterdir())==[]


def test_collection_continues_after_http_failure(source,raw_pdf,tmp_path,monkeypatch):
    monkeypatch.setitem(SOURCES,'falha',{**SOURCES[source],'url':'https://example.test/failure'})
    def respond(request):
        return httpx.Response(503) if request.url.path=='/failure' else httpx.Response(200,content=raw_pdf)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report=collect(['falha',source],tmp_path,client)
    assert [r['status'] for r in report['documentos']]==['erro','extraido']
    index=(tmp_path/'indice.md').read_text(encoding='utf-8')
    assert report['documentos'][1]['markdown'] in index
    assert (tmp_path/'manifesto.json').exists()


def test_disk_failure_keeps_previous_valid_snapshot(source,raw_pdf,tmp_path,monkeypatch):
    path=ingest(source,raw_pdf,tmp_path)
    before=path.read_bytes()
    def fail(*args,**kwargs):
        raise OSError('disco cheio')
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(OSError):
        ingest(source,raw_pdf+b'\n',tmp_path)
    assert path.read_bytes()==before
    assert not list(tmp_path.rglob('.coleta-*'))


def test_pdf_accepts_explicit_technical_source_metadata(source,raw_pdf,tmp_path):
    info={**SOURCES[source],'camada':'A','publicador':'SVRS','catalog_url':'https://example.test/tecnica'}
    path=ingest(source,raw_pdf,tmp_path,source_info=info)
    meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
    assert meta['camada']=='A' and meta['publicador']=='SVRS'
    assert meta['catalog_url']=='https://example.test/tecnica'
    assert 'camada A' in path.read_text(encoding='utf-8')
