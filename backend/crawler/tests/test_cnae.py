import hashlib
import json
from datetime import datetime, timezone

import httpx
import pytest

from backend.crawler.cnae import SOURCE_URL, fetch_cnaes, ingest, parse_cnaes


@pytest.fixture
def payload():
    return [{"id": "0111301", "descricao": "Cultivo de arroz", "classe": {
        "id": "01113", "descricao": "Cultivo de cereais", "grupo": {
            "id": "011", "descricao": "Produção de lavouras temporárias", "divisao": {
                "id": "01", "descricao": "Agricultura", "secao": {
                    "id": "A", "descricao": "Agricultura, pecuária e serviços relacionados"}}}}}]


def test_preserves_codes_and_hierarchy(payload):
    records = parse_cnaes(json.dumps(payload).encode())
    assert records[0]["codigo"] == "0111301"
    assert records[0]["descricao"] == "Cultivo de arroz"
    assert records[0]["hierarquia"] == payload[0]["classe"]


@pytest.mark.parametrize("body", [b'not json', b'[]', b'{}', b'[null]'])
def test_rejects_invalid_response(body):
    with pytest.raises(ValueError):
        parse_cnaes(body)


@pytest.mark.parametrize("field,value", [("id", 111301), ("id", "123"), ("descricao", " "), ("classe", {})])
def test_rejects_invalid_record(payload, field, value):
    payload[0][field] = value
    with pytest.raises(ValueError):
        parse_cnaes(json.dumps(payload).encode())


def test_rejects_duplicate_code(payload):
    with pytest.raises(ValueError, match="duplicado"):
        parse_cnaes(json.dumps(payload * 2).encode())


def test_rejects_missing_hierarchy(payload):
    del payload[0]["classe"]["grupo"]["divisao"]["secao"]
    with pytest.raises(ValueError):
        parse_cnaes(json.dumps(payload).encode())


def test_fetches_official_endpoint(payload):
    def respond(request):
        assert str(request.url) == SOURCE_URL
        return httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        raw = fetch_cnaes(client)
    assert json.loads(raw) == payload


def test_http_error_does_not_ingest(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            raw = fetch_cnaes(client)
            ingest(raw, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_invalid_payload_does_not_write_files(tmp_path):
    with pytest.raises(ValueError):
        ingest(b'[]', tmp_path)
    assert list(tmp_path.iterdir()) == []



def test_markdown_snapshot_is_traceable_and_repeatable(payload, tmp_path):
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    collected = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    path = ingest(raw, tmp_path, collected_at=collected)
    markdown = path.read_text(encoding='utf-8')
    assert path.name == 'cnaes.md'
    assert hashlib.sha256(raw).hexdigest() in markdown
    assert SOURCE_URL in markdown
    assert '2026-11-03T12:00:00+00:00' in markdown
    assert 'quantidade_registros: 1' in markdown
    assert '## 0111301 — Cultivo de arroz' in markdown
    assert '| Seção | A | Agricultura, pecuária e serviços relacionados |' in markdown
    assert (path.parent / 'original.json').read_bytes() == raw
    assert ingest(raw, tmp_path) == path
    assert path.read_text(encoding='utf-8') == markdown
    assert len(list(tmp_path.iterdir())) == 1


def test_changed_content_keeps_previous_snapshot(payload, tmp_path):
    first = ingest(json.dumps(payload).encode(), tmp_path)
    payload[0]['descricao'] = 'Descrição atualizada'
    second = ingest(json.dumps(payload).encode(), tmp_path)
    assert first != second
    assert first.exists() and second.exists()


def test_markdown_escapes_table_and_preserves_optional_details(payload, tmp_path):
    payload[0]['classe']['descricao'] = 'Cereais | grãos\nCultivo'
    payload[0]['atividades'] = ['Cultivo de arroz']
    payload[0]['observacoes'] = ['Inclui arroz\nNão inclui beneficiamento']
    path = ingest(json.dumps(payload).encode(), tmp_path)
    markdown = path.read_text(encoding='utf-8')
    assert 'Cereais &#124; grãos Cultivo' in markdown
    assert '### Atividades' in markdown and '- Cultivo de arroz' in markdown
    assert '### Observações' in markdown and 'Não inclui beneficiamento' in markdown


def test_disk_failure_does_not_publish_partial_snapshot(payload, tmp_path, monkeypatch):
    from pathlib import Path
    original_write = Path.write_text
    def fail_markdown(path, *args, **kwargs):
        if path.name == 'cnaes.md':
            raise OSError('disco cheio')
        return original_write(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', fail_markdown)
    with pytest.raises(OSError, match='disco cheio'):
        ingest(json.dumps(payload).encode(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_invalid_new_response_keeps_previous_snapshot(payload, tmp_path):
    first = ingest(json.dumps(payload).encode(), tmp_path)
    previous = first.read_bytes()
    with pytest.raises(ValueError):
        ingest(b'[]', tmp_path)
    assert first.read_bytes() == previous
    assert len(list(tmp_path.iterdir())) == 1


def test_corrupt_existing_snapshot_is_reported(payload, tmp_path):
    raw = json.dumps(payload).encode()
    path = ingest(raw, tmp_path)
    (path.parent / 'original.json').write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='divergente'):
        ingest(raw, tmp_path)
