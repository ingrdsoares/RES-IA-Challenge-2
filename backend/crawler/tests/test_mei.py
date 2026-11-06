import json
import httpx
from backend.crawler import mei

def test_coleta_preserva_original_e_continua_apos_falha(tmp_path,monkeypatch):
 monkeypatch.setattr(mei,'SOURCES',{'falha':{'title':'Falha','url':'https://example.test/falha','identity':['MEI']},'mei':{'title':'MEI','url':'https://example.test/mei','identity':['MEI'],'camada':'B','kind':'orientacao_mei'}})
 raw=b'<html><h1>MEI</h1><div id="content-core"><p>Orientacao MEI</p></div></html>'
 def handler(request):return httpx.Response(404 if request.url.path=='/falha' else 200,content=raw)
 with httpx.Client(transport=httpx.MockTransport(handler)) as client:report=mei.collect(['falha','mei'],tmp_path,client)
 assert [i['status'] for i in report['fontes']]==['erro','extraido']
 path=tmp_path/report['fontes'][1]['markdown']
 assert (path.parent/'original.html').read_bytes()==raw
 assert json.loads((tmp_path/'manifesto.json').read_text(encoding='utf-8'))['total']==2
 assert report['fontes'][1]['camada']=='B'


def test_layout_volto_extrai_somente_texto_editorial():
 from backend.crawler.paginas import parse_page
 raw=b'<html><h1>MEI</h1><nav>Menu</nav><div id="page-document"><p>Requisito editorial MEI</p><div class="block html"><div></div></div></div></html>'
 result=parse_page(raw,{'identity':['MEI'],'url':'https://example.test/mei'})
 assert 'Requisito editorial MEI' in result['markdown']
 assert 'Menu' not in result['markdown']


def test_retentativa_falha_recupera_snapshot_sem_erro_ativo(tmp_path,monkeypatch):
 monkeypatch.setattr(mei,'SOURCES',{'mei':{'title':'MEI','url':'https://example.test/mei','identity':['MEI']}})
 raw=b'<html><h1>MEI</h1><div id="content-core"><p>Orientacao MEI</p></div></html>'
 with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw))) as client:mei.collect(['mei'],tmp_path,client)
 with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(503))) as client:report=mei.collect(['mei'],tmp_path,client)
 item=report['fontes'][0]
 assert item['status']=='extraido'
 assert item['historico'][0]['resultado']=='falha_na_retentativa'
 assert 'erro' in item['historico'][0]
 assert 'erro' not in item
