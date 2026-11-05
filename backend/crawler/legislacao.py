"""Coleta legislação oficial em Markdown, sem inferir vigência."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import httpx
from markdownify import markdownify

SOURCES = {
    'lc123': {
        'title': 'Lei Complementar nº 123, de 14 de dezembro de 2006',
        'url': 'https://www2.camara.leg.br/legin/fed/leicom/2006/leicomplementar-123-14-dezembro-2006-548099-normaatualizada-pl.html',
        'reader_url': 'https://www2.camara.leg.br/legin/fed/leicom/2006/leicomplementar-123-14-dezembro-2006-548099-normaatualizada-pl.html',
        'format': 'html', 'view': 'texto_atualizado_camara',
    },
    'lgpd': {
        'title': 'Lei nº 13.709, de 14 de agosto de 2018 — LGPD',
        'url': 'https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html',
        'reader_url': 'https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html',
        'format': 'html', 'view': 'texto_atualizado_camara',
    },
    'ec132': {
        'title': 'Emenda Constitucional nº 132, de 20 de dezembro de 2023',
        'url': 'https://www2.camara.leg.br/legin/fed/emecon/2023/emendaconstitucional-132-20-dezembro-2023-795084-publicacaooriginal-170513-pl.html',
        'reader_url': 'https://www2.camara.leg.br/legin/fed/emecon/2023/emendaconstitucional-132-20-dezembro-2023-795084-publicacaooriginal-170513-pl.html',
        'format': 'html', 'view': 'publicacao_original_camara', 'content_selector': '.textoNorma', 'line_article_headings': True,
    },
    'lc214': {
        'title': 'Lei Complementar nº 214, de 16 de janeiro de 2025',
        'url': 'https://www2.camara.leg.br/legin/fed/leicom/2025/leicomplementar-214-16-janeiro-2025-796905-normaatualizada-pl.html',
        'reader_url': 'https://www2.camara.leg.br/legin/fed/leicom/2025/leicomplementar-214-16-janeiro-2025-796905-normaatualizada-pl.html',
        'format': 'html', 'view': 'texto_atualizado_camara',
    },
    'ctn': {
        'title': 'Lei nº 5.172, de 25 de outubro de 1966 — Código Tributário Nacional',
        'url': 'https://www2.camara.leg.br/legin/fed/lei/1960-1969/lei-5172-25-outubro-1966-358971-normaatualizada-pl.html',
        'reader_url': 'https://www2.camara.leg.br/legin/fed/lei/1960-1969/lei-5172-25-outubro-1966-358971-normaatualizada-pl.html',
        'format': 'html', 'view': 'texto_atualizado_camara',
    },
    'lc116': {
        'title': 'Lei Complementar nº 116, de 31 de julho de 2003 — ISS e lista de serviços',
        'url': 'https://www2.camara.leg.br/legin/fed/leicom/2003/leicomplementar-116-31-julho-2003-492028-normaatualizada-pl.html',
        'reader_url': 'https://www2.camara.leg.br/legin/fed/leicom/2003/leicomplementar-116-31-julho-2003-492028-normaatualizada-pl.html',
        'format': 'html', 'view': 'texto_atualizado_camara',
    },
    'cgsn140': {
        'title': 'Resolução CGSN nº 140, de 22 de maio de 2018',
        'url': 'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/92278/visao/multivigente',
        'reader_url': 'https://normasinternet2.receita.fazenda.gov.br/#/consulta/externa/92278/visao/multivigente',
        'format': 'json', 'view': 'multivigente',
    },
}
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'legislacao'
ARTICLE = re.compile(r'^Art\.\s*\d+(?:[º°o])?(?:-[A-Z]+)?', re.I)


def _convert(markup: str, base_url: str) -> str:
    soup = BeautifulSoup(markup, 'html.parser')
    for node in soup(['script', 'style', 'nav', 'header', 'footer']):
        node.decompose()
    for link in soup.find_all('a', href=True):
        href = link['href']
        if base_url == SOURCES['cgsn140']['reader_url'] and re.fullmatch(r'\d+(?:#.*)?', href):
            number, _, anchor = href.partition('#')
            link['href'] = f'https://normasinternet2.receita.fazenda.gov.br/#/consulta/externa/{number}/visao/multivigente' + (f'?segmento={anchor}' if anchor else '')
        else:
            link['href'] = urljoin(base_url, href)
    for node in soup.find_all('strike'):
        node.name = 'del'
    for node in soup.find_all(style=True):
        if 'line-through' in node['style'] and node.name not in ('s', 'strike', 'del'):
            wrapper = soup.new_tag('del')
            node.wrap(wrapper)
    return markdownify(str(soup), heading_style='ATX', bullets='-', strip=['img']).strip()


def _parse_camara(raw: bytes, source: str, identity_pattern: str) -> str:
    # Câmara declara UTF-8 no HTML; não depender de heurísticas de encoding.
    soup = BeautifulSoup(raw.decode('utf-8-sig'), 'html.parser')
    plain = ' '.join(soup.get_text(' ', strip=True).split())
    if not re.search(identity_pattern, plain, re.I):
        raise ValueError(f'Resposta não identifica a norma esperada: {SOURCES[source]["title"]}.')
    selector = SOURCES[source].get('content_selector')
    if selector:
        content = soup.select_one(selector)
        if content is None:
            raise ValueError('Bloco de texto normativo não encontrado.')
        soup = BeautifulSoup(str(content), 'html.parser')
    if SOURCES[source].get('line_article_headings'):
        for block in soup.find_all('dir'):
            block.name = 'div'
        markdown = _convert(str(soup), SOURCES[source]['reader_url'])
        pattern = r'(?m)^[ \t\u00a0]*(Art\.\s*\d+(?:[º°o])?(?:-[A-Z]+)?\.?)(?=\s)'
        markdown, count = re.subn(pattern, lambda m: f'## {m[1]}\n\n{m[1]}', markdown)
        if not count:
            raise ValueError('Norma sem artigos reconhecíveis; revisar o HTML.')
        return markdown
    count = 0
    for paragraph in list(soup.find_all('p')):
        if paragraph.find_parent('table'):
            continue
        text = ' '.join(paragraph.get_text(' ', strip=True).split())
        article = ARTICLE.match(text)
        annex = re.fullmatch(r'ANEXO\s+[IVXLCDM]+(?:\s+.*)?', text, re.I)
        if article or annex:
            heading = soup.new_tag('h2')
            heading.string = article.group() if article else text
            paragraph.insert_before(heading)
            count += bool(article)
    if count == 0:
        raise ValueError('Norma sem artigos reconhecíveis; revisar o HTML.')
    return _convert(str(soup), SOURCES[source]['reader_url'])



def parse_lc123(raw: bytes) -> str:
    return _parse_camara(raw, 'lc123', r'LEI COMPLEMENTAR N[º°o]?\s*123,?\s*DE 14 DE DEZEMBRO DE 2006')


def parse_lgpd(raw: bytes) -> str:
    return _parse_camara(raw, 'lgpd', r'LEI N[º°o]?\s*13\.?709,?\s*DE 14 DE AGOSTO DE 2018')



def parse_ec132(raw: bytes) -> str:
    return _parse_camara(raw, 'ec132', r'EMENDA CONSTITUCIONAL N[º°o]?\s*132,?\s*DE 2023')


def parse_lc214(raw: bytes) -> str:
    return _parse_camara(raw, 'lc214', r'LEI COMPLEMENTAR N[º°o]?\s*214,?\s*DE 16 DE JANEIRO DE 2025')



def parse_ctn(raw: bytes) -> str:
    return _parse_camara(raw, 'ctn', r'LEI N[º°o]?\s*5\.?172,?\s*DE 25 DE OUTUBRO DE 1966')



def parse_lc116(raw: bytes) -> str:
    markdown = _parse_camara(raw, 'lc116', r'LEI COMPLEMENTAR N[º°o]?\s*116,?\s*DE 31 DE JULHO DE 2003')
    paragraphs = [' '.join(p.get_text(' ', strip=True).split())
                  for p in BeautifulSoup(raw.decode('utf-8-sig'), 'html.parser').find_all('p')]
    if not any('Lista de serviços anexa' in p for p in paragraphs) or not any(re.match(r'^\d{1,2}\.\d{2}\s*[-–]', p) for p in paragraphs):
        raise ValueError('Norma sem lista de serviços reconhecível; revisar o HTML.')
    return markdown


def parse_cgsn140(raw: bytes) -> str:
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get('idAto') != 92278
            or data.get('visao') != 'multivigente' or data.get('integro') is not True):
        raise ValueError('Resposta não corresponde à CGSN 140 multivigente integral.')
    segments = data.get('outrosSegmentos')
    ementas = data.get('ementas', [])
    if not isinstance(segments, list) or not segments or not isinstance(ementas, list):
        raise ValueError('Resolução sem segmentos reconhecíveis.')
    lines, seen, articles = [], set(), 0
    for segment in sorted(ementas + segments, key=lambda s: s['ordemSegmentoAto']):
        sid = segment['idSegmento']
        version = segment.get('versaoSegmento', 1)
        key = (sid, version)
        text = segment['textoIntegra']
        if not isinstance(sid, int) or not isinstance(version, int) or key in seen or not isinstance(text, str):
            raise ValueError('Segmento inválido ou duplicado na resolução.')
        seen.add(key)
        plain = ' '.join(BeautifulSoup(text, 'html.parser').get_text(' ', strip=True).split())
        article = ARTICLE.match(plain)
        articles += bool(article)
        label = article.group() if article else 'Segmento'
        lines.extend([f'## {label} — segmento-{sid}-v{version}', ''])
        flags = [title for field, title in [('tachado', 'TACHADO NA FONTE'),
                 ('agendado', 'AGENDADO NA FONTE'), ('omitir', 'MARCADO PARA OMISSÃO NA FONTE')]
                 if segment.get(field)]
        if flags:
            lines.extend(['> ' + '; '.join(flags) + '. Preservado para revisão histórica.', ''])
        lines.extend([_convert(text, SOURCES['cgsn140']['reader_url']), ''])
        attachment = segment.get('arquivoBinario')
        if attachment:
            aid = attachment['idArquivoBinario']
            name = str(attachment['nomeArquivoBinario']).replace('[', '').replace(']', '')
            url = f'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/92278/anexo/{aid}'
            lines.extend([f'Anexo externo: [{name}]({url})', '',
                          '> O arquivo não foi baixado nem convertido nesta etapa.', ''])
    if not articles:
        raise ValueError('Resolução sem artigos reconhecíveis.')
    return '\n'.join(lines)


def ingest(source: str, raw: bytes, output: Path, *, collected_at: datetime | None = None) -> Path:
    info = SOURCES[source]
    body = {'lc123': parse_lc123, 'lgpd': parse_lgpd, 'cgsn140': parse_cgsn140, 'ec132': parse_ec132, 'lc214': parse_lc214, 'ctn': parse_ctn, 'lc116': parse_lc116}[source](raw)
    instant = collected_at or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('Data da coleta deve incluir fuso horário.')
    digest = hashlib.sha256(raw).hexdigest()
    parent = Path(output) / source
    target = parent / digest
    original_name = 'original.' + info['format']
    result = target / 'legislacao.md'
    if target.exists():
        if (target / original_name).read_bytes() != raw or not result.is_file():
            raise ValueError('Versão existente incompleta ou divergente.')
        return result
    content = '\n'.join(['---', f'source_id: {source}', f'source_url: {info["url"]}',
        f'consulta_url: {info["reader_url"]}', 'camada: A', f'visao: {info["view"]}',
        f'coletado_em: {instant.astimezone(timezone.utc).isoformat()}', f'sha256: {digest}',
        'vigencia: nao_verificada', 'revisao_humana: pendente', '---', '', f'# {info["title"]}', '',
        f'[Arquivo original]({original_name})', '',
        '> Documento coletado para pesquisa. A data de coleta não comprova vigência. Texto histórico, alterações e efeitos futuros exigem revisão antes do uso em regras fiscais.', '', body, ''])
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.coleta-', dir=parent))
    try:
        (staging / original_name).write_bytes(raw)
        (staging / 'legislacao.md').write_text(content, encoding='utf-8')
        try:
            staging.rename(target)
        except FileExistsError:
            if (target / original_name).read_bytes() != raw or not result.is_file():
                raise ValueError('Versão concorrente incompleta ou divergente.')
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=[*SOURCES, 'all'], default='all')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--input', type=Path, help='Reprocessar HTML/JSON oficial salvo, sem rede.')
    args = parser.parse_args()
    if args.input and args.source == 'all':
        parser.error('--input exige --source diferente de all.')
    failed = False
    with httpx.Client(timeout=60, follow_redirects=True,
                      headers={'User-Agent': 'SocioDigital-Crawler/0.1'}) as client:
        for source in SOURCES if args.source == 'all' else [args.source]:
            try:
                if args.input:
                    raw = args.input.read_bytes()
                else:
                    response = client.get(SOURCES[source]['url'])
                    response.raise_for_status()
                    raw = response.content
                path = ingest(source, raw, args.output)
                print(f'{source}: {path.resolve()}')
            except (httpx.HTTPError, ValueError, OSError, KeyError, TypeError) as exc:
                print(f'Falha em {source}: {exc}', file=sys.stderr)
                failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
