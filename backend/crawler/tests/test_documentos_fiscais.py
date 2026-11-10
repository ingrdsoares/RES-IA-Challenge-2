import io
import json
import zipfile
import httpx

from backend.crawler.documentos_fiscais import SOURCES, collect


def test_collection_reports_http_failure_and_extracts_remaining_xsd(tmp_path,monkeypatch):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('nota.xsd','<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:test"><xs:element name="Nota" type="xs:string"/></xs:schema>')
    info={'title':'XSD de teste','url':'https://example.test/ok.zip','catalog_url':'https://example.test',
          'format':'zip','identity_namespace':'urn:test'}
    monkeypatch.setitem(SOURCES,'teste',info)
    monkeypatch.setitem(SOURCES,'falha',{**info,'url':'https://example.test/fail.zip'})
    def respond(request):
        return httpx.Response(503) if request.url.path=='/fail.zip' else httpx.Response(200,content=stream.getvalue())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report=collect(['falha','teste'],tmp_path,client)
    assert [r['status'] for r in report['documentos']]==['erro','extraido']
    result=report['documentos'][1]
    assert (tmp_path/result['markdown']).exists()
    assert result['markdown'] in (tmp_path/'indice.md').read_text(encoding='utf-8')
    assert json.loads((tmp_path/'manifesto.json').read_text(encoding='utf-8'))['total']==2
