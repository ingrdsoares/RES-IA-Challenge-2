import hashlib,json
import pytest
from backend.crawler.complemento_contabil import extract_articles,ingest_civil

def fixture():
 return ('<html><p>Lei 10.406</p>'+''.join(f'<p>Art. {n:,}. Texto {n}</p><p>Parágrafo preservado {n}</p>'.replace(',','.') for n in range(1178,1197))+'</html>').encode()

def test_recorte_preserva_todos_os_artigos_e_exclui_vizinhos(tmp_path):
 raw=fixture();path=ingest_civil(raw,tmp_path);text=path.read_text(encoding='utf-8');meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
 assert meta['artigos']==list(range(1179,1196))
 assert meta['sha256']==hashlib.sha256(raw).hexdigest()
 assert (path.parent/'original.html').read_bytes()==raw
 assert 'Texto 1178' not in text and 'Texto 1196' not in text
 assert 'Parágrafo preservado 1180' in text
 assert ingest_civil(raw,tmp_path)==path

def test_recorte_rejeita_incompleto():
 with pytest.raises(ValueError,match='incompleto'):extract_articles(fixture().replace(b'Art. 1.180',b'Sem artigo'))
