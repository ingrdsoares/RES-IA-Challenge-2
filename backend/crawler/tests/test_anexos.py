import hashlib
import json
from pathlib import Path

import httpx
import pytest

from backend.crawler.anexos import collect, extract_pdf, ingest, list_attachments


@pytest.fixture
def raw_pdf():
    return (Path(__file__).parent / 'fixtures/cgsn140-anexo-i.pdf').read_bytes()


@pytest.fixture
def source():
    return {'idAto': 92278, 'visao': 'multivigente', 'integro': True, 'ementas': [],
        'outrosSegmentos': [
            {'idSegmento': 10, 'versaoSegmento': 1, 'ordemSegmentoAto': 1,
             'textoIntegra': 'Anexo I', 'tachado': True, 'agendado': False,
             'arquivoBinario': {'idArquivoBinario': 48430, 'nomeArquivoBinario': 'Anexo I.pdf'}},
            {'idSegmento': 10, 'versaoSegmento': 2, 'ordemSegmentoAto': 2,
             'textoIntegra': 'Anexo I', 'tachado': False, 'agendado': True,
             'arquivoBinario': {'idArquivoBinario': 48431, 'nomeArquivoBinario': 'Anexo I novo.pdf'}}]}


def test_catalog_preserves_historical_versions(source):
    refs = list_attachments(json.dumps(source).encode())
    assert len(refs) == 2
    assert refs[0]['tachado'] is True
    assert refs[1]['agendado'] is True
    assert refs[0]['versao_segmento'] == 1 and refs[1]['versao_segmento'] == 2
    assert refs[0]['url'].endswith('/92278/anexo/48430')


@pytest.mark.parametrize('field,value', [('idAto', 1), ('visao', 'vigente'), ('integro', False), ('outrosSegmentos', [])])
def test_catalog_rejects_wrong_source(source, field, value):
    source[field] = value
    with pytest.raises(ValueError):
        list_attachments(json.dumps(source).encode())


def test_pdf_extracts_real_values_and_tables(raw_pdf):
    pages = extract_pdf(raw_pdf)
    assert len(pages) == 1
    assert '180.000,00' in pages[0]['texto']
    assert len(pages[0]['tabelas']) == 2
    assert any('4,00%' in row for table in pages[0]['tabelas'] for row in table)
    assert any('378.000,00' in row for table in pages[0]['tabelas'] for row in table)


@pytest.mark.parametrize('raw', [b'', b'<html>Acesso negado</html>', b'%PDF-not-a-pdf'])
def test_invalid_pdf_is_rejected(raw):
    with pytest.raises(ValueError):
        extract_pdf(raw)


def test_snapshot_keeps_original_metadata_and_reuses_version(source, raw_pdf, tmp_path):
    ref = list_attachments(json.dumps(source).encode())[0]
    path = ingest(ref, raw_pdf, tmp_path, source_sha256='a'*64)
    meta = json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
    assert (path.parent/'original.pdf').read_bytes() == raw_pdf
    assert meta['sha256'] == hashlib.sha256(raw_pdf).hexdigest()
    assert meta['source_sha256'] == 'a'*64
    assert meta['paginas'] == 1 and meta['tabelas'] == 2
    assert meta['tachado'] is True
    md = path.read_text(encoding='utf-8')
    assert 'TACHADO NA FONTE' in md and '## Página 1' in md
    assert '| Coluna 1 | Coluna 2 |' in md
    before = path.read_bytes()
    assert ingest(ref, raw_pdf, tmp_path, source_sha256='a'*64) == path
    assert path.read_bytes() == before


def test_http_failure_is_reported_and_other_annex_is_collected(source, raw_pdf, tmp_path):
    def respond(request):
        return httpx.Response(503) if str(request.url).endswith('48430') else httpx.Response(200,content=raw_pdf)
    source_raw = json.dumps(source).encode()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report = collect(source_raw, tmp_path, client)
    assert [r['status'] for r in report['arquivos']] == ['erro', 'extraido']
    root = tmp_path/hashlib.sha256(source_raw).hexdigest()
    assert (root/'indice.md').exists()
    assert list(root.glob('48431/*/original.pdf'))
    assert not list(root.glob('48430/*/original.pdf'))


def test_disk_failure_never_publishes_partial_snapshot(source, raw_pdf, tmp_path, monkeypatch):
    ref=list_attachments(json.dumps(source).encode())[0]
    def fail(*args, **kwargs):
        raise OSError('disco cheio')
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(OSError):
        ingest(ref,raw_pdf,tmp_path,source_sha256='a'*64)
    assert not list(tmp_path.glob('*/*/original.pdf'))
    assert not list(tmp_path.rglob('.coleta-*'))


def test_blank_pdf_keeps_original_and_marks_ocr_pending(source, tmp_path):
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R /Resources << >> >>',
               b'<< /Length 0 >>\nstream\n\nendstream']
    raw = b'%PDF-1.4\n'
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(raw)
    raw += b'xref\n0 5\n0000000000 65535 f \n'
    raw += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    raw += f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
    ref = list_attachments(json.dumps(source).encode())[0]
    path = ingest(ref, raw, tmp_path, source_sha256='a'*64)
    meta = json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
    assert meta['status'] == 'ocr_pendente'
    assert meta['paginas_sem_texto'] == [1]
    assert 'OCR PENDENTE' in path.read_text(encoding='utf-8')
    assert (path.parent/'original.pdf').read_bytes() == raw


def test_rejects_repeated_attachment_instead_of_losing_provenance(source):
    source['outrosSegmentos'][1]['arquivoBinario']['idArquivoBinario'] = 48430
    with pytest.raises(ValueError, match='repetido'):
        list_attachments(json.dumps(source).encode())
