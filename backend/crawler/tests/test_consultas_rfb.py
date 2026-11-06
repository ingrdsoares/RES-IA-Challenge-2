import json
import httpx
import pytest
from backend.crawler import consultas_rfb as c


def row(aid):
    return {'idAto': aid, 'tipoAto': {'idTipoAto': 72}}


def test_parser_rejects_error_unrelated_type_and_wrong_identity():
    for value in ({'message': 'erro'}, {'atos': [{'idAto':1,'tipoAto':{'idTipoAto':1}}], 'quantidadeTotal':1,'quantidadePaginas':1}):
        with pytest.raises(ValueError): c.parse_page(json.dumps(value).encode())
    with pytest.raises(ValueError): c.parse_detail(b'{"idAto":2}',1)


def test_all_pages_cross_theme_dedup_resume_integrity(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'TERMS',{'simples':'Simples','mei':'MEI'})
    calls=[]
    def transport(req):
        p=json.loads(req.content);calls.append(p)
        ids=[1,2] if p['paginacaoPaginaAtual']==1 else [3]
        return httpx.Response(200,json={'atos':[row(i) for i in ids],'quantidadeTotal':3,'quantidadePaginas':2})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        found,report=c.discover(client,tmp_path,delay=0)
        assert len(found)==3 and all(x['completa'] for x in report.values())
        assert found[3]['temas']==['simples','mei'] and len(calls)==4
        c.discover(client,tmp_path,delay=0)
        assert len(calls)==4
        (tmp_path/'listagens/simples/0001.json').write_bytes(b'{}')
        with pytest.raises(ValueError,match='Cache divergente'): c.discover(client,tmp_path,delay=0)


def test_duplicate_page_rejected_and_explicit_limit_recorded(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'TERMS',{'x':'x'})
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'atos':[row(1)],'quantidadeTotal':2,'quantidadePaginas':2}))) as client:
        found,report=c.discover(client,tmp_path,delay=0,max_pages=1)
        assert len(found)==1 and report['x']['completa'] is False
        with pytest.raises(ValueError,match='repetidos'): c.discover(client,tmp_path,delay=0)


def test_retries_and_error_never_cached(tmp_path):
    calls=[]
    def transport(req):
        calls.append(1)
        return httpx.Response(503 if len(calls)<3 else 200,content=b'original')
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        assert c.cached(client,tmp_path/'a','GET','https://example.org',delay=0)==b'original'
    assert len(calls)==3
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(403))) as client:
        with pytest.raises(httpx.HTTPStatusError): c.cached(client,tmp_path/'b','GET','https://example.org',delay=0)
    assert not (tmp_path/'b').exists()


def test_source_flags_relations_and_attachments_retained():
    s=dict(idSegmento=9,versaoSegmento=2,ordemSegmentoAto=1,textoIntegra='<p>VINCULADA à SC 1.</p>',tachado=True,ancorasOrigem=[{'idAto':2}],ancorasDestino=[],arquivoBinario={'idArquivoBinario':7})
    text,refs,relations=c.render_segments({'ementas':[s],'outrosSegmentos':[]})
    assert 'VINCULADA à SC 1.' in text and 'tachado' in text
    assert list(refs)==[7] and relations[0]['ancorasOrigem']==[{'idAto':2}]
    with pytest.raises(ValueError,match='PDF'): c.extract_pdf(b'<html>erro</html>')


def test_ingest_preserves_original_and_warns_integral_not_verified(tmp_path):
    detail={'idAto':7,'visao':'multivigente','integro':True,'epigrafeCompleta':'Solução de Consulta Cosit 1',
        'epigrafe':{'orgaos':[{'siglaOrgao':'Cosit'}],'numeroAto':'1','dataAto':'2020-01-01','tipoAto':{'idTipoAto':72}},
        'ementas':[dict(idSegmento=1,versaoSegmento=1,ordemSegmentoAto=1,textoIntegra='<p>Assunto: Simples Nacional</p>')],
        'outrosSegmentos':[],'historico':[{'texto':'Vinculação original'}]}
    original=json.dumps(detail,ensure_ascii=False).encode('utf8')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=original))) as client:
        meta=c.ingest(client,tmp_path,{'row':{'idAto':7,'ementa':'Simples Nacional'},'temas':['simples']},delay=0)
    assert (tmp_path/'7/original.json').read_bytes()==original
    assert meta['originais'][0]['sha256']==c.digest(original)
    assert meta['texto_integral_verificado'] is False and meta['vigencia']=='nao_verificada'
    assert meta['historico_fonte']==detail['historico']
    text=(tmp_path/'7/documento.md').read_text(encoding='utf8')
    assert 'camada: B' in text and 'não comprova' in text


def test_pdfium_extracts_pages_with_source_text():
    # PDF mínimo com texto real, sem depender de rede nem dos dados coletados.
    content=b'BT /F1 12 Tf 20 100 Td (Simples Nacional - Fator R) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream']
    pdf=b'%PDF-1.4\n';offsets=[0]
    for n,obj in enumerate(objects,1):
        offsets.append(len(pdf));pdf+=str(n).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(pdf)
    pdf+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    pdf+=b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF'
    assert c.extract_pdf(pdf)==['Simples Nacional - Fator R']


def test_ingest_pdf_metadata_and_cached_text_reuse(tmp_path,monkeypatch):
    detail={'idAto':7,'visao':'multivigente','integro':True,'epigrafeCompleta':'SC 1',
        'epigrafe':{'orgaos':[],'numeroAto':'1','dataAto':'2020-01-01','tipoAto':{'idTipoAto':72}},
        'ementas':[],'outrosSegmentos':[dict(idSegmento=1,versaoSegmento=1,ordemSegmentoAto=1,textoIntegra='Anexo',arquivoBinario={'idArquivoBinario':8,'nomeArquivoBinario':'sc.pdf'})]}
    calls=[]
    monkeypatch.setattr(c,'extract_pdf',lambda pdf:calls.append(pdf) or ['Texto original'])
    def response(req):
        return httpx.Response(200,content=b'%PDF-fake' if '/anexo/' in str(req.url) else json.dumps(detail).encode())
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        item={'row':{'idAto':7},'temas':['mei']}
        first=c.ingest(client,tmp_path,item,delay=0)
        second=c.ingest(client,tmp_path,item,delay=0)
    assert len(calls)==1 and not second['falhas_anexos']
    assert first['anexos'][0]['extrator']=='pypdfium2'
    assert first['anexos'][0]['versao_extrator']
    assert len(first['originais'])==2
    assert '[PDF original 8](8.pdf)' in (tmp_path/'7/documento.md').read_text(encoding='utf8')


def test_original_view_fallback_keeps_error_evidence_and_resumes(tmp_path):
    detail={'idAto':7,'visao':'exclusiva','ehVisaoExclusiva':True,'integro':False,'epigrafeCompleta':'SC 1',
        'epigrafe':{'orgaos':[],'numeroAto':'1','dataAto':'2020-01-01','tipoAto':{'idTipoAto':72}},'ementas':[],'outrosSegmentos':[]}
    calls=[]
    def response(req):
        calls.append(str(req.url))
        return httpx.Response(406,json={'message':'Consulte original'}) if str(req.url).endswith('multivigente') else httpx.Response(200,json=detail)
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        item={'row':{'idAto':7},'temas':['mei']}
        meta=c.ingest(client,tmp_path,item,delay=0)
        c.ingest(client,tmp_path,item,delay=0)
    assert len(calls)==2 and meta['visao_fonte']=='exclusiva'
    assert (tmp_path/'7/visao-indisponivel.json').is_file()
    assert meta['source_url'].endswith('/original')
    assert meta['markdown_sha256']==c.digest((tmp_path/'7/documento.md').read_bytes())
