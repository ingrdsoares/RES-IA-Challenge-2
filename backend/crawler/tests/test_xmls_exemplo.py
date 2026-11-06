import io
import json
import zipfile

import httpx
import pytest
from backend.crawler.xmls_exemplo import SOURCES, collect, inventory, package_members

NS = 'http://www.portalfiscal.inf.br/nfe'


def archive(files):
    target = io.BytesIO()
    with zipfile.ZipFile(target, 'w') as z:
        for name, value in files.items():
            z.writestr(name, value)
    return target.getvalue()


@pytest.mark.parametrize('model,kind', [('55', 'NF-e'), ('65', 'NFC-e')])
def test_nfe_identity_environment(model, kind):
    doc = inventory(f'<NFe xmlns="{NS}" versao="4.00"><infNFe><ide><mod>{model}</mod><tpAmb>2</tpAmb></ide></infNFe></NFe>'.encode(), NS)
    assert doc['tipo_documento'] == kind
    assert doc['ambiente'] == 'homologacao'
    assert doc['assinatura_validada'] is False
    assert doc['validacao_xsd'].startswith('nao_realizada')


@pytest.mark.parametrize('root', ['DPS', 'NFSe', 'evento'])
def test_nfse_document_types(root):
    ns = 'http://www.sped.fazenda.gov.br/nfse'
    assert inventory(f'<{root} xmlns="{ns}" versao="1.01"/>'.encode(), ns)['tipo_documento'] == root


@pytest.mark.parametrize('raw', [b'<!DOCTYPE X><X/>', b'<!DOCTYPE X [<!ENTITY test "oops">]><X>&test;</X>', b'<broken>'])
def test_reject_unsafe_xml(raw):
    with pytest.raises(ValueError):
        inventory(raw, '')


def test_reject_namespace_and_missing_model():
    with pytest.raises(ValueError, match='Namespace'):
        inventory(b'<NFe/>', NS)
    with pytest.raises(ValueError, match='modelo'):
        inventory(f'<NFe xmlns="{NS}"/>'.encode(), NS)


@pytest.mark.parametrize('name', ['../escape.xml', 'C:/escape.xml', '/escape.xml', 'x:stream.xml', 'x/../../escape.xml', 'x\\..\\escape.xml'])
def test_reject_zip_traversal(name):
    with pytest.raises(ValueError):
        package_members(archive({name: '<x/>'}))


def test_schema_is_not_invoice():
    assert package_members(archive({'note.xsd': '<schema/>'})) == {}


def test_collect_preserves_original_and_idempotent(tmp_path):
    ns = SOURCES['sp-nfse-exemplos']['namespace']
    raw = archive({'Exemplo/retorno.txt': f'<RetornoConsulta xmlns="{ns}"><Cabecalho Versao="2"/></RetornoConsulta>'})
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=raw)))
    first = collect(['sp-nfse-exemplos'], tmp_path, client)
    second = collect(['sp-nfse-exemplos'], tmp_path, client)
    assert first['documentos'] == second['documentos']
    assert first['arquivos_xml'] == 1
    meta = first['documentos'][0]
    from pathlib import Path
    assert Path(meta['originais'][0]['arquivo']).read_bytes() == raw
    assert meta['documentos'][0]['versoes_internas'] == ['2']
    assert json.loads((tmp_path / 'manifesto.json').read_text(encoding='utf-8'))['falhas'] == 0


def test_failed_download_is_reported(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(503)))
    assert collect(['sp-nfse-exemplos'], tmp_path, client)['falhas'] == 1


def test_cache_repairs_modified_xml(tmp_path):
    from pathlib import Path
    ns = SOURCES['sp-nfse-exemplos']['namespace']
    raw = archive({'sample.xml': f'<RetornoConsulta xmlns="{ns}"/>'})
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=raw)))
    report = collect(['sp-nfse-exemplos'], tmp_path, client)
    target = Path(report['documentos'][0]['documentos'][0]['arquivo'])
    target.write_bytes(b'corrupted')
    repaired = collect(['sp-nfse-exemplos'], tmp_path, client)
    assert target.read_bytes() != b'corrupted'
    assert repaired['falhas'] == 0
