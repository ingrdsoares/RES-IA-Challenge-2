"""Recorte documental SPED: ECD, ECF, EFD-Contribuições e EFD-ICMS/IPI."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import httpx
from backend.crawler.anexos import _write_atomic
from backend.crawler.obrigacoes_avancadas import api, official, parse_json, pdf_text
from backend.crawler.paginas import normalize

BASE = 'https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'sped-complementar'
LIMITES = ('Catálogos e manuais oficiais, camada B. Disponibilização documental não comprova vigência nem incidência da obrigação para todo MEI, Simples Nacional ou empresa. '
           'EFD-ICMS/IPI possui aplicação estadual a conferir; jurisdição documental: federal/SPED. '
           'Texto PDF por página; tabelas e imagens não reconstruídas. Revisão humana pendente. Recorte finito sem histórico completo, tabelas dinâmicas ou softwares.')
FAMILIES = {
    'ecd': ('manuais-e-documentos-tecnicos', 'manual_de_orientacao_da_ecd_leiaute_9_janeiro_2026.pdf', ['ecd', 'leiaute 9'], 'Leiaute 9; janeiro/2026; ADE Cofis 1/2026'),
    'ecf': ('manuais-e-documentos-tecnicos', 'manual_ecf_leiaute_12_20_05_2026_ac_2025_sit_esp_2026.pdf', ['ecf', 'leiaute 12'], 'Leiaute 12; atualização 23/07/2026; AC2025/situações especiais2026'),
    'efd-contribuicoes': ('manuais', 'guia_pratico_efd_contribuicoes_versao_1_35-18_06_2021.pdf', ['contribuicoes', '1.35'], '1.35; 18/06/2021; listado no catálogo consultado2026'),
    'efd-icms-ipi': ('manuais-e-documentos-tecnicos', 'guia-pratico-efd-versao-3-2-4.pdf', ['icms', '3.2.4'], '3.2.4; atualização 30/07/2026'),
}
SOURCES = {}
for family, (catalog, filename, identity, version) in FAMILIES.items():
    url = BASE + family
    cat = url + '/' + catalog
    common = {'familia': family, 'publicador': 'Receita Federal / SPED', 'jurisdicao': 'federal/SPED', 'catalog_url': cat}
    SOURCES[family + '-orientacoes'] = {**common, 'title': family + ' — orientações oficiais', 'url': api(url), 'kind': 'json', 'identity': [family.split('-')[0]], 'versao_documental': 'página consultada2026'}
    SOURCES[family + '-catalogo'] = {**common, 'title': family + ' — catálogo de manuais', 'url': api(cat) + '?b_size=100', 'kind': 'json', 'identity': ['manuais'], 'versao_documental': 'catálogo consultado2026'}
    SOURCES[family + '-manual'] = {**common, 'title': family + ' — manual/guia ' + version, 'url': cat + '/' + filename + '/@@download/file', 'kind': 'pdf', 'identity': identity, 'versao_documental': version}


def ingest(source_id, info, raw, output):
    if not official(info['url']):
        raise ValueError('Fonte fora do domínio oficial permitido.')
    digest = hashlib.sha256(raw).hexdigest()
    target = Path(output) / source_id / digest
    if target.exists():
        return validate_cache(target, info)
    if info['kind'] == 'json':
        text, extra = parse_json(raw, info)
        ext = 'json'
    elif info['kind'] == 'pdf':
        pages = pdf_text(raw)
        initial = normalize(' '.join(pages[:3]))
        if not all(normalize(token) in initial for token in info['identity']):
            raise ValueError('PDF não corresponde à identidade documental esperada.')
        text = '\n\n'.join(f'## Página {n}\n\n{page}' for n, page in enumerate(pages, 1))
        extra = {'paginas': len(pages), 'paginas_sem_texto': [n for n, page in enumerate(pages, 1) if not page.strip()], 'extrator': 'pypdfium2',
                 'limite_extracao': 'Texto por página; tabelas e imagens não reconstruídas.'}
        ext = 'pdf'
    else:
        raise ValueError('Formato não suportado; HTML shell não constitui documento.')
    original = 'original.' + ext
    meta = {**{k: v for k, v in info.items() if k != 'identity'}, 'source_id': source_id, 'source_url': info['url'], 'titulo': info['title'],
            'sha256': digest, 'bytes': len(raw), 'coletado_em': datetime.now(timezone.utc).isoformat(), 'original': original,
            'markdown_file': 'documento.md', 'camada': 'B', 'tipo': 'manual' if ext == 'pdf' else 'catalogo_ou_orientacao',
            'status': 'ocr_pendente' if extra.get('paginas_sem_texto') else 'extraido', 'vigencia': 'nao_verificada', 'revisao_humana': 'pendente', **extra}
    markdown = f'# {info["title"]}\n\n{LIMITES}\n\nFonte: {info["url"]}\n\n{str(text)}\n'
    meta['artefatos_sha256'] = {'documento.md': hashlib.sha256(markdown.encode()).hexdigest()}
    meta['originais'] = [{'arquivo': (target / original).resolve().as_posix(), 'source_url': info['url'], 'sha256': digest, 'bytes': len(raw)}]
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.coleta-', dir=target.parent))
    try:
        (staging / original).write_bytes(raw)
        (staging / 'documento.md').write_text(markdown, encoding='utf-8', newline='\n')
        (staging / 'metadados.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        staging.rename(target)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return target / 'documento.md'


def validate_cache(target, info):
    meta = json.loads((target / 'metadados.json').read_text(encoding='utf-8'))
    original = target / meta['original']
    if meta['source_url'] != info['url'] or hashlib.sha256(original.read_bytes()).hexdigest() != meta['sha256'] or original.stat().st_size != meta['bytes']:
        raise ValueError('Cache original divergente.')
    for name, digest in meta['artefatos_sha256'].items():
        if hashlib.sha256((target / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Cache derivado divergente.')
    return target / meta['markdown_file']


def collect(sources, output, client, refresh=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for source_id in sources:
        info = SOURCES[source_id]
        try:
            existing = sorted((output / source_id).glob('*/metadados.json'))
            if existing and not refresh:
                newest = max(existing, key=lambda p: json.loads(p.read_text(encoding='utf-8'))['coletado_em'])
                path = validate_cache(newest.parent, info)
                reused = True
            else:
                response = client.get(info['url'])
                response.raise_for_status()
                if not official(str(response.url)):
                    raise ValueError('Redirecionamento fora da fonte oficial.')
                path = ingest(source_id, info, response.content, output)
                reused = False
            meta = json.loads((path.parent / 'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta, 'markdown': path.relative_to(output).as_posix(), 'reutilizado': reused})
        except (httpx.HTTPError, ValueError, OSError, KeyError) as exc:
            results.append({'source_id': source_id, 'source_url': info['url'], 'status': 'erro', 'erro': str(exc), 'revisao_humana': 'pendente'})
        print(source_id + ': ' + results[-1]['status'], flush=True)
    report = {'executado_em': datetime.now(timezone.utc).isoformat(), 'limites': LIMITES, 'total': len(results),
              'sucesso': sum(r['status'] == 'extraido' for r in results), 'pendencias': sum(r['status'] == 'ocr_pendente' for r in results),
              'erros': sum(r['status'] == 'erro' for r in results), 'reutilizados': sum(r.get('reutilizado', False) for r in results),
              'paginas': sum(r.get('paginas', 0) for r in results), 'documentos': results}
    _write_atomic(output / 'manifesto.json', json.dumps(report, ensure_ascii=False, indent=2))
    lines = ['# SPED complementar — quatro famílias', '', LIMITES, '', f'Fontes: {report["total"]}; extraídas: {report["sucesso"]}; pendências: {report["pendencias"]}; erros: {report["erros"]}; páginas: {report["paginas"]}.', '', '| Fonte | Versão documental | Estado | Páginas |', '|---|---|---|---|']
    for result in results:
        title = result['source_id']
        if 'markdown' in result: title = f'[{title}]({result["markdown"]})'
        lines.append(f'| {title} | {result.get("versao_documental", "")} | {result["status"]} | {result.get("paginas", "")} |')
        if 'erro' in result: lines.append('\nFalha: ' + result['erro'] + '\n')
    _write_atomic(output / 'indice.md', '\n'.join(lines) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=[*SOURCES, 'all'], default='all')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--refresh', action='store_true', help='Consultar novamente fontes remotas; snapshots anteriores preservados.')
    args = parser.parse_args()
    with httpx.Client(timeout=120, follow_redirects=True, headers={'User-Agent': 'SocioDigital-Crawler/0.1'}) as client:
        report = collect(list(SOURCES) if args.source == 'all' else [args.source], args.output, client, args.refresh)
    print(f'Fontes: {report["total"]}; páginas: {report["paginas"]}; erros: {report["erros"]}; pendências: {report["pendencias"]}; reutilizados: {report["reutilizados"]}')
    return int(report['erros'] > 0 or report['pendencias'] > 0)


if __name__ == '__main__':
    raise SystemExit(main())
