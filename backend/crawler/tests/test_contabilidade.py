import json
from pathlib import Path
import httpx

from backend.crawler.contabilidade import SOURCES, collect


def test_collect_preserves_technical_reference_layer_and_reports_http_failure(tmp_path,monkeypatch):
    raw=(Path(__file__).parent/'fixtures/cgsn140-anexo-i.pdf').read_bytes()
    info={'title':'Norma técnica de teste','url':'https://example.test/norma.pdf',
        'catalog_url':'https://example.test/catalogo','identity':['anexo i'],
        'kind':'norma_contabil','camada':'C','publicador':'CFC'}
    monkeypatch.setitem(SOURCES,'teste',info)
    monkeypatch.setitem(SOURCES,'falha',{**info,'url':'https://example.test/erro.pdf'})
    def respond(request):
        return httpx.Response(503) if request.url.path=='/erro.pdf' else httpx.Response(200,content=raw)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report=collect(['falha','teste'],tmp_path,client)
    assert [item['status'] for item in report['normas']]==['erro','extraido']
    result=report['normas'][1]
    assert result['camada']=='C' and result['publicador']=='CFC'
    path=tmp_path/result['markdown']
    assert (path.parent/'original.pdf').read_bytes()==raw
    assert result['markdown'] in (tmp_path/'indice.md').read_text(encoding='utf-8')
    before=path.read_bytes()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        collect(['teste'],tmp_path,client)
    assert path.read_bytes()==before


def test_wrong_document_is_not_published(tmp_path,monkeypatch):
    raw=(Path(__file__).parent/'fixtures/cgsn140-anexo-i.pdf').read_bytes()
    info={'title':'ITG 1000 (2022)','url':'https://example.test/norma.pdf',
        'catalog_url':'https://example.test/catalogo','identity':['itg 1000','2022'],
        'kind':'norma_contabil','camada':'C','publicador':'CFC'}
    monkeypatch.setitem(SOURCES,'teste',info)
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw))) as client:
        report=collect(['teste'],tmp_path,client)
    assert report['normas'][0]['status']=='erro'
    assert not list(tmp_path.glob('teste/*/documento.md'))
