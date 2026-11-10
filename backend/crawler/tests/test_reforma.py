import httpx
from backend.crawler.reforma import SOURCES,collect


def test_collection_keeps_original_view_and_continues_after_a_law_failure(tmp_path):
    ec='<h1>EMENDA CONSTITUCIONAL Nº 132, DE 2023</h1><div class="textoNorma"><p>Art. 1º Alterações constitucionais.</p></div>'.encode()
    calendar='<h1>Cronograma dos documentos fiscais eletrônicos</h1><div id="content-core"><table><tr><td>01/01/2027</td><td>Publicação do leiaute</td></tr></table></div>'.encode()
    def respond(request):
        if str(request.url)==SOURCES['ec132']['url']:return httpx.Response(200,content=ec)
        if str(request.url)==SOURCES['cronograma']['url']:return httpx.Response(200,content=calendar)
        return httpx.Response(503)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report=collect(list(SOURCES),tmp_path,client)
    assert [s['status'] for s in report['fontes']]==['extraido','erro','extraido']
    assert report['fontes'][0]['visao']=='publicacao_original_camara'
    assert report['fontes'][2]['camada']=='B' and report['fontes'][2]['tabelas']==1
    index=(tmp_path/'indice.md').read_text(encoding='utf-8')
    assert report['fontes'][2]['markdown'] in index
    assert '01/01/2027' in (tmp_path/report['fontes'][2]['markdown']).read_text(encoding='utf-8')
