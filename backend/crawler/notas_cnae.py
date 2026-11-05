"""Notas explicativas integrais da CNAE-Subclasses 2.3, publicação IBGE 2020."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import httpx

from backend.crawler.anexos import _write_atomic
from backend.crawler.cnae import SOURCE_URL as API_URL, parse_cnaes
from backend.crawler.manuais import ingest

PDF_URL = 'https://www.ibge.gov.br/biblioteca/visualizacao/livros/liv101721.pdf'
CATALOG_URL = 'https://www.ibge.gov.br/estatisticas/metodos-e-classificacoes/classificacoes-e-listas-estatisticas/9078-.html'
FTP_URL = 'https://ftp.ibge.gov.br/Informacoes_Gerais_e_Referencia/Classificacoes/CNAE/cnae2_3/'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'notas-cnae'
INFO = {'title': 'CNAE-Subclasses 2.3 — notas explicativas (IBGE, 2020)',
        'url': PDF_URL, 'catalog_url': CATALOG_URL, 'identity': ['2 3', 'ibge'],
        'kind': 'notas_explicativas_cnae', 'publicador': 'IBGE / CONCLA', 'camada': 'A'}


def parse_notes(markdown: str) -> list[dict]:
    """Indexa os títulos de subclasses somente na Parte 3 da edição de 2020.

    Páginas físicas 101–528 (impressas 99–526). Não inclui a estrutura sem
    notas da Parte 2 nem códigos citados nas tabelas de correspondência.
    O texto integral e a hierarquia permanecem no Markdown por página.
    """
    records = {}
    for number, body in re.findall(r'(?m)^## Página (\d+)\n(.*?)(?=^## Página |\Z)', markdown, re.S | re.M):
        page = int(number)
        if not 101 <= page <= 528:
            continue
        body = body.split('### Tabela ', 1)[0]
        for match in re.finditer(r'(?m)^(?:[A-U][ \t]+)?(\d{4}-\d/\d{2})[^\S\n]+([^\n]+)$', body):
            code = re.sub(r'\D', '', match[1])
            if code in records:
                raise ValueError(f'Título de subclasse repetido na Parte 3: {code}.')
            title = [match[2]]
            for continuation in body[match.end():].splitlines():
                continuation = continuation.strip()
                if not continuation:
                    continue
                if re.match(r'(?:Esta subclasse|```|[-#|]|(?:[A-U] +)?\d)', continuation):
                    break
                if re.fullmatch(r'[A-U]', continuation):
                    continue  # letra da seção do cabeçalho lateral
                title.append(continuation)
            records[code] = {'codigo': code, 'codigo_formatado': match[1],
                             'titulo': ' '.join(title), 'pagina_pdf_inicio': page}
    if not records:
        raise ValueError('Nenhum título de subclasse encontrado na Parte 3.')
    return sorted(records.values(), key=lambda item: item['codigo'])


def coverage(notes: list[dict], api_raw: bytes) -> dict:
    api = {record['codigo'] for record in parse_cnaes(api_raw)}
    pdf = {record['codigo'] for record in notes}
    return {'subclasses_pdf': len(pdf), 'subclasses_api': len(api),
            'comuns': len(pdf & api), 'somente_pdf': sorted(pdf-api),
            'somente_api': sorted(api-pdf),
            'cobertura_completa_api': pdf == api}


def collect(output: Path, client: httpx.Client) -> dict:
    output = Path(output)
    pdf = client.get(PDF_URL)
    pdf.raise_for_status()
    path = ingest('cnae-subclasses-2.3-2020', pdf.content, output, source_info=INFO)
    document = path.read_text(encoding='utf-8')
    notes = parse_notes(document)
    if '978-65-87201-07-8' not in document or len(notes) != 1332:
        raise ValueError('Publicação CNAE 2.3/2020 divergente do ISBN ou das 1.332 subclasses esperadas.')
    api = client.get(API_URL)
    api.raise_for_status()
    comparison = coverage(notes, api.content)
    root = path.parent
    digest = hashlib.sha256(api.content).hexdigest()
    api_dir = output/'comparacao-api'/digest
    api_dir.mkdir(parents=True, exist_ok=True)
    api_path = api_dir/'original.json'
    if not api_path.exists():
        api_path.write_bytes(api.content)
    _write_atomic(api_dir/'metadados.json', json.dumps({'source_id': 'ibge-cnae-comparacao-notas', 'source_url': API_URL, 'coletado_em': datetime.now(timezone.utc).isoformat(), 'sha256': digest, 'status': 'extraido', 'revisao_humana': 'pendente'}, ensure_ascii=False, indent=2))
    meta = json.loads((root/'metadados.json').read_text(encoding='utf-8'))
    if meta['paginas'] != 608:
        raise ValueError('Publicação CNAE 2.3/2020 deve conter 608 páginas físicas.')
    meta.update({'paginas_em_branco_verificadas': [8, 12, 40, 42, 98, 100, 530, 598],
        'paginas_graficas_sem_texto': [607],
        'observacao_ocr': 'Página 607 é contracapa com contatos IBGE em contornos vetoriais; notas da Parte 3 integralmente textuais. Brancos sem objetos e contracapa conferidos.',
        'status_notas': 'extraido', 'versao_classificacao': '2.3', 'ano_publicacao': 2020,
        'intervalo_notas_paginas_pdf': [101, 528], 'cobertura': comparison,
        'status_versao': '2.3 identificada no catálogo oficial; vigência não inferida da coleta',
        'tipo_conteudo': 'classificacao_economica; nao_e_anexo_tributario'})
    _write_atomic(root/'metadados.json', json.dumps(meta, ensure_ascii=False, indent=2))
    _write_atomic(root/'subclasses.json', json.dumps(notes, ensure_ascii=False, indent=2))
    report = {'executado_em': datetime.now(timezone.utc).isoformat(),
        'source_url': PDF_URL, 'catalog_url': CATALOG_URL, 'ftp_url': FTP_URL,
        'versao': '2.3', 'ano_publicacao': 2020, 'documentos': [{**meta,
        'markdown': path.relative_to(output).as_posix()}],
        'comparacao_api': {'source_url': API_URL, 'sha256': digest,
          'original': api_path.relative_to(output).as_posix(), **comparison},
        'limites': ['Índice automático por título de subclasse; notas de seções, divisões, grupos e classes preservadas no documento integral.',
          'Notas podem continuar na página seguinte; consultar páginas adjacentes.',
          'Não substitui enquadramento tributário. Revisão humana da extração pendente.']}
    lines = ['# Notas explicativas da CNAE-Subclasses 2.3', '',
        f'[Catálogo IBGE]({CATALOG_URL}) · [Downloads oficiais]({FTP_URL})', '',
        f'[Publicação integral de 2020]({path.relative_to(output).as_posix()}) — {meta["paginas"]} páginas físicas.', '',
        '> O extrator genérico marca nove páginas sem texto: oito brancas e a contracapa gráfica (607), conferidas. Não há página sem texto no intervalo das notas.', '',
        f'Parte 3: páginas físicas 101–528; {len(notes)} títulos de subclasses. Cobertura API: {comparison["comuns"]}/{comparison["subclasses_api"]}.', '',
        '> A classificação estatística CNAE 2.0 e a CNAE-Subclasses 2.3 têm versões distintas. Esta coleta é da publicação de subclasses 2.3. O PDF integral inclui introdução, estrutura e correspondências históricas; não são anexos tributários. Revisão humana pendente.', '',
        '| Código | Título extraído | Página física inicial |', '|---|---|---|']
    for item in notes:
        title = item['titulo'].replace('|', '&#124;')
        lines.append(f'| {item["codigo_formatado"]} | {title} | [{item["pagina_pdf_inicio"]}]({path.relative_to(output).as_posix()}#página-{item["pagina_pdf_inicio"]}) |')
    _write_atomic(output/'manifesto.json', json.dumps(report, ensure_ascii=False, indent=2))
    _write_atomic(output/'indice.md', '\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        report = collect(args.output, client)
    print(json.dumps(report['comparacao_api'], ensure_ascii=False, indent=2))
    return int(not report['comparacao_api']['cobertura_completa_api'])


if __name__ == '__main__':
    raise SystemExit(main())
