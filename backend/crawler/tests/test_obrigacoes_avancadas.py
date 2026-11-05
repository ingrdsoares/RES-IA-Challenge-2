import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx
import pytest
from backend.crawler import obrigacoes_avancadas as ob


def info(kind='json', identity=None):
    return ob.source('EFD-Reinf', 'https://www.gov.br/sped/teste',identity or ['reinf'],kind)


def payload():
    return json.dumps({'title':'EFD-Reinf','description':'Orientações oficiais '*20,
                       'items':[{'title':'Manual','@id':'https://www.gov.br/sped/manual.pdf'}]}).encode()


def test_json_original_hash_metadata_and_resume(tmp_path):
    raw=payload();path=ob.ingest('teste',info(),raw,tmp_path)
    meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
    assert meta['sha256']==hashlib.sha256(raw).hexdigest()
    assert (path.parent/'original.json').read_bytes()==raw
    assert meta['revisao_humana']=='pendente' and meta['vigencia']=='nao_verificada'
    before=path.read_bytes()
    assert ob.ingest('teste',info(),raw,tmp_path)==path
    assert path.read_bytes()==before
    (path.parent/'original.json').write_bytes(b'corrupto')
    with pytest.raises(ValueError,match='divergente'):ob.ingest('teste',info(),raw,tmp_path)


@pytest.mark.parametrize('raw',[
    b'{"title":"Outro"}',
    b'{"title":"EFD-Reinf","items":[]}',
    b'{"title":"EFD-Reinf","items_total":5,"items":[{}]}',
    b'{"title":"EFD-Reinf","items":[{"@id":"https://example.org/a","title":"manual"}]}',
])
def test_json_identity_empty_pagination_external_rejected(raw):
    with pytest.raises(ValueError):ob.parse_json(raw,info())


def test_html_shell_not_manual(tmp_path):
    with pytest.raises(ValueError):
        ob.ingest('shell',info('html'),b'<h1>EFD-Reinf</h1><div id="content">Carregando</div>',tmp_path)
    assert not list(tmp_path.iterdir())


def test_pdf_extraction_and_identity(tmp_path):
    raw=(Path(__file__).parent/'fixtures/cgsn140-anexo-i.pdf').read_bytes()
    assert 'ANEXO' in ob.pdf_text(raw)[0]
    with pytest.raises(ValueError,match='identidade'):
        ob.ingest('errado',info('pdf',['inexistente']),raw,tmp_path)
    with pytest.raises(ValueError,match='PDF'):ob.pdf_text(b'<html>erro</html>')


def test_zip_filters_non_pdf_and_prevents_traversal():
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('a.pdf',b'%PDF-1.7')
        z.writestr('notes.txt',b'nota')
    assert ob.pdf_members(buf.getvalue())==[('a.pdf',b'%PDF-1.7')]
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:z.writestr('../a.pdf',b'%PDF-1.7')
    with pytest.raises(ValueError,match='inseguro'):ob.pdf_members(buf.getvalue())


def test_collect_continues_http_failure_and_manifest(tmp_path,monkeypatch):
    monkeypatch.setitem(ob.SOURCES,'ok',info())
    monkeypatch.setitem(ob.SOURCES,'bad',{**info(),'url':'https://www.gov.br/failure'})
    def respond(request):
        return httpx.Response(503) if request.url.path=='/failure' else httpx.Response(200,content=payload())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report=ob.collect(['bad','ok'],tmp_path,client)
    assert report['erros']==1 and report['sucesso']==1
    assert [x['status'] for x in report['documentos']]==['erro','extraido']
    assert 'Falha bad' in (tmp_path/'indice.md').read_text(encoding='utf-8')


def test_unofficial_source_rejected(tmp_path):
    with pytest.raises(ValueError,match='oficial'):
        ob.ingest('x',{**info(),'url':'https://www.gov.br.example.org/x'},payload(),tmp_path)


def test_source_selection_excludes_future_production():
    assert '26/10/2026' in ob.SOURCES['esocial-xsd']['versao_documental']
    assert all('2026-11-23' not in x['url'] for x in ob.SOURCES.values())
