"""Coleta manual de subclasses CNAE do IBGE para Markdown rastreável."""

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

import httpx

SOURCE_URL = 'https://servicodados.ibge.gov.br/api/v2/cnae/subclasses'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'cnae'


def parse_cnaes(raw: bytes) -> list[dict]:
    """Valida toda a resposta antes de permitir qualquer gravação."""
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('Resposta do IBGE não contém JSON válido.') from exc
    if not isinstance(data, list) or not data:
        raise ValueError('Esperada uma lista não vazia de CNAEs.')
    records, seen = [], set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError('Registro CNAE inválido.')
        code, description = item.get('id'), item.get('descricao')
        if not isinstance(code, str) or not re.fullmatch(r'[0-9]{7}', code):
            raise ValueError('Código CNAE deve conter sete dígitos textuais.')
        if code in seen:
            raise ValueError(f'Código CNAE duplicado: {code}.')
        seen.add(code)
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f'Descrição ausente no CNAE {code}.')
        node = item
        for level, pattern in [('classe', r'[0-9]{5}'), ('grupo', r'[0-9]{3}'),
                               ('divisao', r'[0-9]{2}'), ('secao', r'[A-U]')]:
            node = node.get(level)
            if (not isinstance(node, dict)
                    or not isinstance(node.get('id'), str)
                    or not re.fullmatch(pattern, node['id'])
                    or not isinstance(node.get('descricao'), str)
                    or not node['descricao'].strip()):
                raise ValueError(f'Hierarquia {level} inválida no CNAE {code}.')
        for field in ('atividades', 'observacoes'):
            values = item.get(field, [])
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ValueError(f'Campo {field} inválido no CNAE {code}.')
        records.append({'codigo': code, 'descricao': description,
                        'hierarquia': item['classe'],
                        'atividades': item.get('atividades', []),
                        'observacoes': item.get('observacoes', [])})
    return sorted(records, key=lambda record: record['codigo'])


def fetch_cnaes(client: httpx.Client) -> bytes:
    response = client.get(SOURCE_URL)
    response.raise_for_status()
    return response.content


def _text(value: str) -> str:
    value = html.escape(' '.join(value.split()), quote=False)
    return value.replace('|', '&#124;').replace('*', '&#42;').replace('_', '&#95;').replace('`', '&#96;').replace('[', '&#91;').replace(']', '&#93;')


def ingest(raw: bytes, output: Path, *, collected_at: datetime | None = None) -> Path:
    records = parse_cnaes(raw)
    collected_at = collected_at or datetime.now(timezone.utc)
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError('Data da coleta deve incluir fuso horário.')
    digest = hashlib.sha256(raw).hexdigest()
    output = Path(output)
    destination = output / digest
    markdown_path = destination / 'cnaes.md'
    if destination.exists():
        if (destination / 'original.json').read_bytes() != raw or not markdown_path.is_file():
            raise ValueError('Versão existente incompleta ou divergente; revisar os arquivos.')
        return markdown_path
    lines = ['---', 'source_id: ibge-cnae-subclasses', f'source_url: {SOURCE_URL}',
             'camada: A', f'coletado_em: {collected_at.astimezone(timezone.utc).isoformat()}',
             f'sha256: {digest}', f'quantidade_registros: {len(records)}',
             'vigencia: nao_verificada', '---', '', '# CNAE — subclasses do IBGE', '',
             '[Resposta original](original.json)', '',
             'A data acima representa a coleta. CNAE sozinho não determina elegibilidade MEI, anexo ou tributação.', '']
    for record in records:
        lines.extend([f"## {record['codigo']} — {_text(record['descricao'])}", '',
                      '| Nível | Código | Descrição |', '|---|---|---|'])
        node = record['hierarquia']
        hierarchy = [('Classe', node)]
        for label, key in [('Grupo', 'grupo'), ('Divisão', 'divisao'), ('Seção', 'secao')]:
            node = node[key]
            hierarchy.append((label, node))
        for label, node in reversed(hierarchy):
            lines.append(f"| {label} | {node['id']} | {_text(node['descricao'])} |")
        lines.append('')
        for field, title in [('atividades', 'Atividades'), ('observacoes', 'Observações')]:
            if record[field]:
                lines.extend([f'### {title}', ''])
                lines.extend(f'- {_text(value)}' for value in record[field])
                lines.append('')
    output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.coleta-', dir=output))
    try:
        (staging / 'original.json').write_bytes(raw)
        (staging / 'cnaes.md').write_text('\n'.join(lines), encoding='utf-8')
        try:
            staging.rename(destination)
        except FileExistsError:
            if (destination / 'original.json').read_bytes() != raw or not markdown_path.is_file():
                raise ValueError('Versão concorrente incompleta ou divergente.')
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT,
                        help='Diretório das versões (padrão: backend/crawler/data/cnae).')
    args = parser.parse_args()
    try:
        with httpx.Client(timeout=60, follow_redirects=True,
                          headers={'User-Agent': 'SocioDigital-Crawler/0.1', 'Accept': 'application/json'}) as client:
            raw = fetch_cnaes(client)
        path = ingest(raw, args.output)
    except (httpx.HTTPError, ValueError, OSError) as exc:
        print(f'Falha na coleta: {exc}', file=sys.stderr)
        return 1
    print(f'Markdown disponível em: {path.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
