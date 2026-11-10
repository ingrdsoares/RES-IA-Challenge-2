import hashlib
import json
from backend.crawler.sumarizacao import build_index,generate
from backend.crawler.catalogo import collect


def test_all_versions_and_receipt_references_are_preserved(tmp_path):
    root=tmp_path/'data';root.mkdir()
    for n in ('a','b'):
        folder=root/'leis'/n;folder.mkdir(parents=True)
        raw=n.encode();(folder/'original.html').write_bytes(raw);(folder/'documento.md').write_text('# Norma '+n,encoding='utf8')
        (folder/'metadados.json').write_text(json.dumps({'source_id':n,'titulo':'Norma '+n,'tipo':'legislacao','source_url':'https://example.gov.br/norma','coletado_em':'2026','sha256':hashlib.sha256(raw).hexdigest()}))
    cache=root/'cache';cache.mkdir();raw=cache/'lista.json';raw.write_bytes(b'{}')
    raw.with_name(raw.name+'.receipt.json').write_text(json.dumps({'source_url':'https://example.gov.br/lista','sha256':hashlib.sha256(b'{}').hexdigest(),'coletado_em':'2026'}))
    index=build_index(root,collect(root))
    assert len(index['entradas'])==2 and len(index['referencias'])==2
    ref=next(r for r in index['referencias'] if r['url'].endswith('/norma'))
    assert len(ref['entradas'])==2 and len(ref['sha256'])==2
    assert not index['erros']
    docs=tmp_path/'docs';report=generate(root,docs,inventory=collect(root),statistics={'snapshots':2})
    assert (docs/'sumarizacao-acervo-tributario.md').exists()
    assert (docs/'referencias-acervo'/'leis.md').exists()
    assert report['entradas']==2 and report['urls']==2
    raw.write_bytes(b'bad')
    assert build_index(root,collect(root))['erros']
