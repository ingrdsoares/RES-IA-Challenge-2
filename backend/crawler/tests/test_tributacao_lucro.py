import base64
import json
import httpx
import pytest
from backend.crawler.tributacao_lucro import parse_html,parse_api,ingest,collect,SOURCES


def html(title='LEI Nº 9.249, DE 26 DE DEZEMBRO DE 1995'):
    return ('<h1>'+title+'</h1><p>Art. 1º Texto <a href="outra.html">link</a> <strike>antigo</strike>.</p><dir><p>Art. 99 Texto citado.</p></dir><p>Art. 1.000 Final.</p><table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>').encode('utf-8')


def api():
    def seg(i,order,text,**extra):
        return dict(idAto=81268,idSegmento=i,versaoSegmento=1,ordemSegmentoAto=order,textoIntegra=text,**extra)
    return dict(idAto=81268,visao='multivigente',integro=True,
        epigrafe=dict(numeroAto='1700',dataAto='2017-03-14',tipoAto={'idTipoAto':42},orgaos=[{'siglaOrgao':'RFB'}]),
        epigrafeCompleta='IN RFB nº 1700, de 14 de março de 2017',ementas=[],
        outrosSegmentos=[seg(2,2,'Art. 2º Depois.',tachado=True),seg(1,1,'Art. 1º Antes <a href="999#x">outra norma</a>.')])


def test_html_identity_links_strike_quotes_and_thousands():
    body,counts=parse_html('lei9249',html())
    assert '## Art. 1.000' in body
    assert '## Art. 99' not in body and '> Art. 99' in body
    assert '~~antigo~~' in body and 'outra.html)' in body
    assert counts=={'artigos':2,'tabelas':1}
    other=html('LEI Nº 9.430, DE 27 DE DEZEMBRO DE 1996').replace(b'<p>Art.', b'<p>Cita LEI N\xc2\xba 9.249, DE 26 DE DEZEMBRO DE 1995</p><p>Art.',1)
    with pytest.raises(ValueError,match='Identidade'):
        parse_html('lei9249',other)


def test_api_order_identity_and_table():
    data=api()
    data['outrosSegmentos'][0]['arquivoBinario']=dict(idArquivoBinario=3,nomeArquivoBinario='tabela.html',arquivoBinario=base64.b64encode(b'<table><tr><td>A</td></tr><tr><td>1</td></tr></table>').decode())
    text,counts=parse_api(json.dumps(data).encode())
    assert text.index('## Art. 1')<text.index('## Art. 2')
    assert 'tachado' in text and 'externa/999/visao/multivigente?segmento=x' in text
    assert counts['segmentos']==2 and counts['tabelas']==1 and '| A |' in text
    for mutate in (lambda d:d.update(idAto=3), lambda d:d['epigrafe'].update(numeroAto='1701'),lambda d:d['outrosSegmentos'][0].update(idAto=99)):
        wrong=api();mutate(wrong)
        with pytest.raises(ValueError,match='Identidade|outro ato'):
            parse_api(json.dumps(wrong).encode())
    duplicate=api();duplicate['outrosSegmentos'].append(duplicate['outrosSegmentos'][0])
    with pytest.raises(ValueError,match='duplicado'):
        parse_api(json.dumps(duplicate).encode())


@pytest.mark.parametrize('damage',['markdown','original','metadata','missing'])
def test_cache_corruption_fails_without_replacing(tmp_path,damage):
    path=ingest('lei9249',html(),tmp_path)
    target=path.parent
    if damage=='markdown':path.write_bytes(b'alterado')
    elif damage=='original':(target/'original.html').write_bytes(b'alterado')
    elif damage=='metadata':(target/'metadados.json').write_text('{}')
    else:(target/'metadados.json').unlink()
    before={p.name:p.read_bytes() for p in target.iterdir()}
    with pytest.raises(ValueError,match='incompleta/corrompida'):
        ingest('lei9249',html(),tmp_path)
    assert {p.name:p.read_bytes() for p in target.iterdir()}==before


def test_ingest_idempotent_and_dataset(tmp_path):
    raw=html();p=ingest('lei9249',raw,tmp_path)
    original_meta=(p.parent/'metadados.json').read_bytes()
    assert ingest('lei9249',raw,tmp_path)==p
    assert (p.parent/'metadados.json').read_bytes()==original_meta
    raws={'lei9249':raw,'lei9430':html('LEI Nº 9.430, DE 27 DE DEZEMBRO DE 1996'),
          'rir9580':html('DECRETO Nº 9.580, DE 22 DE NOVEMBRO DE 2018'),'in1700':json.dumps(api()).encode()}
    mapping={v['url']:raws[k] for k,v in SOURCES.items()}
    def client():return httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=mapping[str(req.url)])))
    first=collect(tmp_path,client());second=collect(tmp_path,client())
    assert first==second and first['coletados']==4 and first['falhas']==0
    assert (p.parent/'metadados.json').read_bytes()==original_meta
