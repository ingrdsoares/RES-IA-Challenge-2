import hashlib
import json
from pathlib import Path

import httpx
import pytest
from backend.crawler import sped_complementar as m


def info(kind='json', identity=None):
    return {**m.SOURCES['ecd-catalogo'], 'kind': kind, 'identity': identity or ['ecd']}


def payload():
    return json.dumps({'title': 'ECD', 'description': 'Orientações documentais oficiais ' * 10,
                       'items': [{'title': 'Manual ECD', '@id': 'https://www.gov.br/sped/manual.pdf'}]}).encode()


@pytest.mark.parametrize('raw', [b'<html>Carregando</html>', b'{"title":"Outra"}', b'{"title":"ECD","items":[]}',
    b'{"title":"ECD","items_total":2,"items":[{"title":"Manual","@id":"https://www.gov.br/a"}]}',
    b'{"title":"ECD","items":[{"title":"Manual","@id":"https://www.gov.br.evil.test/a"}]}'])
def test_reject_shell_identity_pagination_and_untrusted_catalog(raw, tmp_path):
    with pytest.raises(ValueError):
        m.ingest('test', info(), raw, tmp_path)
    assert not list(tmp_path.iterdir())


def test_pdf_masquerade_and_document_identity(tmp_path):
    with pytest.raises(ValueError, match='PDF'):
        m.ingest('fake', info('pdf'), b'<html>ECD manual</html>', tmp_path)
    raw = (Path(__file__).parent / 'fixtures/cgsn140-anexo-i.pdf').read_bytes()
    with pytest.raises(ValueError, match='identidade'):
        m.ingest('wrong', info('pdf', ['ecd', 'leiaute 9']), raw, tmp_path)
    p = m.ingest('pdf', info('pdf', ['anexo']), raw, tmp_path)
    meta = json.loads((p.parent / 'metadados.json').read_text(encoding='utf-8'))
    assert meta['paginas'] > 0 and meta['extrator'] == 'pypdfium2'
    assert 'não reconstruídas' in meta['limite_extracao']


def test_hashes_preservation_and_offline_resume(tmp_path, monkeypatch):
    monkeypatch.setitem(m.SOURCES, 'test', info())
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=payload())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        first = m.collect(['test'], tmp_path, client)
        second = m.collect(['test'], tmp_path, client)
    assert len(calls) == 1
    assert first['sucesso'] == second['sucesso'] == second['reutilizados'] == 1
    meta = second['documentos'][0]
    assert Path(meta['originais'][0]['arquivo']).read_bytes() == payload()
    assert meta['sha256'] == hashlib.sha256(payload()).hexdigest()
    assert meta['camada'] == 'B' and meta['revisao_humana'] == 'pendente'
    (tmp_path / meta['markdown']).write_text('corrupt')
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert m.collect(['test'], tmp_path, client)['erros'] == 1
    assert len(calls) == 1


def test_refresh_preserves_snapshot_and_checks_redirect(tmp_path, monkeypatch):
    monkeypatch.setitem(m.SOURCES, 'test', info())
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=payload()))) as client:
        m.collect(['test'], tmp_path, client)
        report = m.collect(['test'], tmp_path, client, refresh=True)
    assert report['reutilizados'] == 0 and report['sucesso'] == 1
    assert len(list((tmp_path / 'test').iterdir())) == 1
    def redirect(request):
        if request.url.host == 'www.gov.br':
            return httpx.Response(302, headers={'location': 'https://evil.test/'})
        return httpx.Response(200, content=payload())
    with httpx.Client(transport=httpx.MockTransport(redirect), follow_redirects=True) as client:
        assert m.collect(['test'], tmp_path, client, refresh=True)['erros'] == 1



def test_untrusted_source_and_zip_not_supported(tmp_path):
    with pytest.raises(ValueError, match='oficial'):
        m.ingest('x', {**info(), 'url': 'https://example.org/'}, payload(), tmp_path)
    with pytest.raises(ValueError, match='Formato'):
        m.ingest('zip', info('zip'), b'PK', tmp_path)


def test_four_families_twelve_slots():
    assert len(m.SOURCES) == 12
    assert len({s['familia'] for s in m.SOURCES.values()}) == 4
    assert '3.2.4' in m.SOURCES['efd-icms-ipi-manual']['versao_documental']
