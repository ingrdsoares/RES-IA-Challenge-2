"""Baixa e extrai os PDFs dos anexos da CGSN 140 para Markdown."""

import argparse
from datetime import datetime, timezone
import hashlib
import html
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile

import httpx
import pdfplumber

from backend.crawler.legislacao import DEFAULT_OUTPUT as LAW_OUTPUT

DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'anexos-cgsn140'


def list_attachments(raw: bytes) -> list[dict]:
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get('idAto') != 92278
            or data.get('visao') != 'multivigente' or data.get('integro') is not True):
        raise ValueError('Esperada a coleta integral multivigente da CGSN 140.')
    segments = data.get('outrosSegmentos')
    if not isinstance(segments, list):
        raise ValueError('Lista de segmentos inválida.')
    refs, seen = [], set()
    for segment in sorted(segments, key=lambda s: s['ordemSegmentoAto']):
        attachment = segment.get('arquivoBinario')
        if not attachment:
            continue
        aid = attachment['idArquivoBinario']
        sid, version = segment['idSegmento'], segment['versaoSegmento']
        if any(type(value) is not int or value <= 0 for value in (aid, sid, version)):
            raise ValueError('Identificador de anexo/segmento inválido.')
        if aid in seen:
            raise ValueError('Arquivo repetido em múltiplas referências; revisar a origem.')
        seen.add(aid)
        name = attachment['nomeArquivoBinario']
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Anexo sem nome.')
        refs.append({'id_arquivo': aid, 'nome': name, 'id_segmento': sid,
            'versao_segmento': version, 'titulo': segment['textoIntegra'],
            'tachado': bool(segment.get('tachado')), 'agendado': bool(segment.get('agendado')),
            'omitir': bool(segment.get('omitir')),
            'url': f'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/92278/anexo/{aid}'})
    if not refs:
        raise ValueError('A coleta não contém anexos.')
    return refs


def extract_pdf(raw: bytes) -> list[dict]:
    if not raw.startswith(b'%PDF-'):
        raise ValueError('Resposta não é um PDF; arquivo vazio ou página de erro.')
    pages = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                tables = page.extract_tables()
                pages.append({'pagina': page.page_number, 'texto': text, 'tabelas': tables})
    except Exception as exc:
        # Fronteira do parser: erros de PDF malformado não interrompem os outros anexos.
        raise ValueError(f'Não foi possível ler o PDF: {exc}') from exc
    if not pages:
        raise ValueError('PDF sem páginas.')
    return pages


def _cell(value) -> str:
    return html.escape(str(value or ''), quote=False).replace('|', '&#124;').replace('\n', '<br>')


def ingest(ref: dict, raw: bytes, output: Path, *, source_sha256: str) -> Path:
    digest = hashlib.sha256(raw).hexdigest()
    parent = Path(output) / str(ref['id_arquivo'])
    target = parent / digest
    result = target / 'anexo.md'
    if target.exists():
        meta = json.loads((target / 'metadados.json').read_text(encoding='utf-8'))
        if ((target / 'original.pdf').read_bytes() != raw or not result.is_file()
                or meta['source_sha256'] != source_sha256 or meta['sha256'] != digest):
            raise ValueError('Versão existente incompleta ou divergente.')
        return result
    pages = extract_pdf(raw)
    missing = [p['pagina'] for p in pages if not p['texto'].strip()]
    meta = {**ref, 'source_sha256': source_sha256, 'sha256': digest,
        'coletado_em': datetime.now(timezone.utc).isoformat(), 'paginas': len(pages),
        'tabelas': sum(len(p['tabelas']) for p in pages), 'paginas_sem_texto': missing,
        'status': 'ocr_pendente' if missing else 'extraido',
        'vigencia': 'nao_verificada', 'revisao_humana': 'pendente',
        'extrator': 'pdfplumber', 'versao_extrator': pdfplumber.__version__}
    lines = ['---', f'id_arquivo: {ref["id_arquivo"]}', f'id_segmento: {ref["id_segmento"]}',
        f'versao_segmento: {ref["versao_segmento"]}', f'source_url: {ref["url"]}',
        f'source_sha256: {source_sha256}', f'sha256: {digest}',
        f'coletado_em: {meta["coletado_em"]}', f'paginas: {len(pages)}', f'tabelas: {meta["tabelas"]}',
        f'status: {meta["status"]}', 'vigencia: nao_verificada', 'revisao_humana: pendente',
        '---', '', '# ' + _cell(ref['nome']), '', '[PDF original](original.pdf) · [Metadados](metadados.json)', '',
        '> Extração automática para pesquisa. Colunas genéricas preservam a posição das células; células mescladas não são inferidas. Conferir o PDF antes de usar os valores em regras fiscais.', '']
    for field, label in [('tachado', 'TACHADO NA FONTE'), ('agendado', 'AGENDADO NA FONTE'),
                         ('omitir', 'MARCADO PARA OMISSÃO NA FONTE')]:
        if ref[field]:
            lines.extend([f'> {label}. Preservado conforme a visão multivigente.', ''])
    for page in pages:
        lines.extend([f'## Página {page["pagina"]}', '', '### Texto extraído', ''])
        if page['texto'].strip():
            fence = '```'
            while fence in page['texto']:
                fence += '`'
            lines.extend([fence + 'text', page['texto'], fence, ''])
        else:
            lines.extend(['> OCR PENDENTE: página sem texto extraível; consultar o PDF original.', ''])
        for number, table in enumerate(page['tabelas'], 1):
            if not table:
                continue
            columns = max(len(row) for row in table)
            lines.extend([f'### Tabela {number}', '',
                '| ' + ' | '.join(f'Coluna {n}' for n in range(1, columns+1)) + ' |',
                '| ' + ' | '.join('---' for _ in range(columns)) + ' |'])
            for row in table:
                cells = list(row) + [''] * (columns-len(row))
                lines.append('| ' + ' | '.join(_cell(cell) for cell in cells) + ' |')
            lines.append('')
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.coleta-', dir=parent))
    try:
        (staging/'original.pdf').write_bytes(raw)
        (staging/'anexo.md').write_text('\n'.join(lines), encoding='utf-8')
        (staging/'metadados.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return result


def _write_atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        try:
            file.write(text)
        except BaseException:
            file.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def collect(source_raw: bytes, output: Path, client: httpx.Client) -> dict:
    refs = list_attachments(source_raw)
    source_hash = hashlib.sha256(source_raw).hexdigest()
    root = Path(output) / source_hash
    root.mkdir(parents=True, exist_ok=True)
    (root/'fonte.json').write_bytes(source_raw)
    results = []
    for ref in refs:
        try:
            response = client.get(ref['url'])
            response.raise_for_status()
            path = ingest(ref, response.content, root, source_sha256=source_hash)
            meta = json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta, 'markdown': path.relative_to(root).as_posix()})
        except (httpx.HTTPError, ValueError, OSError) as exc:
            results.append({**ref, 'status': 'erro', 'erro': str(exc)})
    report = {'source_sha256': source_hash, 'executado_em': datetime.now(timezone.utc).isoformat(),
              'total': len(refs), 'arquivos': results}
    lines = ['# Anexos da Resolução CGSN 140/2018', '',
        f'Fonte: [JSON multivigente](fonte.json) · SHA-256: `{source_hash}`', '',
        '> Inclui versões históricas. Extração automática com revisão de vigência e de tabelas pendente.', '',
        '| Arquivo | Segmento / versão | Marcado como tachado | Estado da extração | Páginas | Tabelas |',
        '|---|---|---|---|---|---|']
    for item in results:
        name = _cell(item['nome'])
        link = f'[{name}]({item["markdown"]})' if 'markdown' in item else name
        lines.append(f'| {link} | {item["id_segmento"]} / {item["versao_segmento"]} | {item["tachado"]} | {item["status"]} | {item.get("paginas", "")} | {item.get("tabelas", "")} |')
        if 'erro' in item:
            lines.extend(['', f'> Falha no arquivo {item["id_arquivo"]}: {_cell(item["erro"])}', ''])
    _write_atomic(root/'manifesto.json', json.dumps(report, ensure_ascii=False, indent=2))
    _write_atomic(root/'indice.md', '\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='original.json da coleta CGSN 140.')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        source_path = args.input
        if source_path is None:
            candidates = list((LAW_OUTPUT/'cgsn140').glob('*/original.json'))
            if len(candidates) != 1:
                raise ValueError('Informe --input: é necessário selecionar uma coleta CGSN 140 quando há zero ou múltiplas versões.')
            source_path = candidates[0]
        with httpx.Client(timeout=60, follow_redirects=True,
                          headers={'User-Agent': 'SocioDigital-Crawler/0.1'}) as client:
            report = collect(source_path.read_bytes(), args.output, client)
        errors = sum(item['status'] != 'extraido' for item in report['arquivos'])
        print(f'Anexos: {report["total"]}; extraídos: {report["total"]-errors}; pendentes/erros: {errors}')
        print(f'Índice: {(args.output/report["source_sha256"]/"indice.md").resolve()}')
        return int(errors > 0)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Falha na coleta de anexos: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
