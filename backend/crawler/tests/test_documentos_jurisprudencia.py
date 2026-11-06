import hashlib
import io
import json
import zipfile
import httpx
import pytest
from backend.crawler import documentos_jurisprudencia as dj
from backend.crawler.tests.test_notas_tecnicas_fiscais import workbook


def item(kind='xlsx',tipo='leiaute_regras_eventos'):
    return dict(source_id='test',titulo='Anexo eventos',url='https://www.gov.br/nfse/test.xlsx',kind=kind,tipo=tipo,catalog_url='https://www.gov.br/nfse')


def test_original_markdown_hash_resume_and_tamper(tmp_path):
    raw=workbook(); meta=dj.ingest(item(),raw,tmp_path)
    target=tmp_path/'test'/meta['sha256']
    assert (target/meta['original']).read_bytes()==raw
    assert meta['originais']==[dict(arquivo=str((target/'original.xlsx').resolve()),sha256=hashlib.sha256(raw).hexdigest(),source_url=item()['url'],bytes=len(raw))]
    assert hashlib.sha256((target/meta['markdown_arquivo']).read_bytes()).hexdigest()==meta['markdown_sha256']
    assert '001.01' in (target/'conteudo.md').read_text(encoding='utf8')
    assert dj.ingest(item(),raw,tmp_path)==meta
    (target/'conteudo.md').write_text('tampered',encoding='utf8')
    with pytest.raises(ValueError,match='divergente'):dj.ingest(item(),raw,tmp_path)


def test_schema_not_instance_and_namespace_validation(tmp_path):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('evento.xsd','<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://www.portalfiscal.inf.br/nfe"><xs:element name="evento" type="xs:string"/></xs:schema>')
    meta=dj.ingest(item('xsd','esquemas_xsd'),buf.getvalue(),tmp_path)
    assert meta['arquivos_xsd']==1 and meta['tipo']=='esquemas_xsd'
    assert 'instâncias XML' in (tmp_path/meta['markdown']).read_text(encoding='utf8')
    assert meta['original']=='original.zip'
    with pytest.raises(ValueError):dj.ingest({**item('xsd'),'source_id':'bad'},b'<NFe/>',tmp_path)


@pytest.mark.parametrize('raw',[b'<html>Login</html>',b'<html><body>Microempreendedores sem decisao</body></html>'])
def test_no_fake_carf_success(tmp_path,raw):
    with pytest.raises(ValueError):dj.ingest(item('html'),raw,tmp_path)
    assert not list(tmp_path.iterdir())


def test_official_and_selection():
    assert not dj.official('https://www.gov.br.evil.org/a')
    assert not dj.official('http://www.gov.br/a')
    assert dj.select('nfe',dict(titulo='Schema CCe',url='https://dfe-portal.svrs.rs.gov.br/Evento_CCe_PL_v1.01.zip'))
    assert not dj.select('nfse',dict(titulo='NBS já coletado',url='https://www.gov.br/anexo_b-nbs2.xlsx'))


def test_collection_records_errors_and_explicit_limits(tmp_path,monkeypatch):
    monkeypatch.setattr(dj,'seeds',lambda:[{**item('pdf'),'url':'https://www.gov.br/fail.pdf'}])
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(503,request=req))) as c:
        report=dj.collect(tmp_path,c)
    assert report['total_extraidos']==0 and report['total']==1
    assert len(report['catalogos'])==2 and all(x['status']=='erro' for x in report['catalogos'])
    assert report['documentos'][0]['status']=='erro'
    assert 'paginação' in report['recorte']
    assert json.loads((tmp_path/'manifesto.json').read_text(encoding='utf8'))['lacunas']

def test_catalog_cache_preserves_first_receipt_and_rejects_tamper(tmp_path):
    raw=b'<html>catalog</html>';chosen=[{'titulo':'Evento','url':'https://www.gov.br/event.zip'}]
    a=dj.save_catalog(tmp_path,'nfe','https://www.gov.br/catalog',raw,chosen,chosen)
    p=tmp_path/'catalogos'/'nfe'/a['sha256'];before={x.name:x.read_bytes() for x in p.iterdir()}
    assert dj.save_catalog(tmp_path,'nfe','https://www.gov.br/catalog',raw,chosen,chosen)==a
    assert before=={x.name:x.read_bytes() for x in p.iterdir()}
    (p/'conteudo.md').write_bytes(b'tampered');modified={x.name:x.read_bytes() for x in p.iterdir()}
    with pytest.raises(ValueError,match='divergente'):dj.save_catalog(tmp_path,'nfe','https://www.gov.br/catalog',raw,chosen,chosen)
    assert modified=={x.name:x.read_bytes() for x in p.iterdir()}


def test_schema_dependency_gap_status_survives_wrapper(tmp_path):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('evt.xsd','<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://www.portalfiscal.inf.br/nfe"><xs:include schemaLocation="missing.xsd"/></xs:schema>')
    m=dj.ingest(item('xsd','esquemas_xsd'),buf.getvalue(),tmp_path)
    assert m['status']=='dependencias_pendentes'
    assert m['dependencias_ausentes'][0]['schemaLocation']=='missing.xsd'
