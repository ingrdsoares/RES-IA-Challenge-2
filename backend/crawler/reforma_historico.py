"""Fotografia oficial da reforma CBS/IBS e do histórico normativo CGSN/MEI."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import httpx
from . import consultas_rfb as rfb
from .legislacao import _convert

DEFAULT_OUTPUT = Path(__file__).parent / 'data' / 'reforma-historico'
QUERIES = {'historico-cgsn': ('CGSN', '67'), 'reforma-cbs': ('CBS', ''), 'reforma-ibs': ('IBS', '')}
PORTALS = {
 'marcos-reforma': 'https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/reforma-tributaria-do-consumo/legislacao',
 'ec132': 'https://www2.camara.leg.br/legin/fed/emecon/2023/emendaconstitucional-132-20-dezembro-2023-795084-publicacaooriginal-170513-pl.html',
 'lc214': 'https://www2.camara.leg.br/legin/fed/leicom/2025/leicomplementar-214-16-janeiro-2025-796905-normaatualizada-pl.html',
 'lc227': 'https://www2.camara.leg.br/legin/fed/leicom/2026/leicomplementar-227-13-janeiro-2026-798657-normaatualizada-pl.html',
 'decreto12955': 'https://www2.camara.leg.br/legin/fed/decret/2026/decreto-12955-29-abril-2026-799019-normaatualizada-pe.html',
}

def parse_search(raw):
    data = json.loads(raw)
    if not isinstance(data.get('atos'), list) or type(data.get('quantidadeTotal')) is not int or type(data.get('quantidadePaginas')) is not int:
        raise ValueError('Paginação oficial inválida')
    ids = [r['idAto'] for r in data['atos']]
    if any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Identidade repetida/inválida')
    return data

def discover(client, output, delay, max_pages):
    found, reports = {}, {}
    for theme, (term, types) in QUERIES.items():
        seen = set()
        for page in range(1, max_pages + 1):
            payload = rfb.search_payload(term, page)
            payload['tiposAtosSelecionados'] = types
            raw = rfb.cached(client, output/'listagens'/theme/f'{page:04}.json', 'POST', rfb.SEARCH, payload=payload, delay=delay)
            data = parse_search(raw)
            current = {r['idAto'] for r in data['atos']}
            if seen & current:
                raise ValueError('Repetição entre páginas')
            seen |= current
            for row in data['atos']:
                if theme == 'historico-cgsn' and not any(o['siglaOrgao'] == 'CGSN' for o in row.get('orgaos', [])):
                    continue
                item = found.setdefault(row['idAto'], {'row': row, 'temas': []})
                item['temas'].append(theme)
            reports[theme] = {'termo': term, 'tipos': types, 'total_fonte': data['quantidadeTotal'], 'paginas_fonte': data['quantidadePaginas'], 'paginas_coletadas': page, 'resultados_lidos': len(seen), 'completa': len(seen) == data['quantidadeTotal'], 'filtro_local': 'órgão CGSN' if theme == 'historico-cgsn' else None}
            if page >= data['quantidadePaginas']:
                break
    rfb.save_json(output/'descoberta.json', {'pesquisas': reports, 'unicos': len(found)})
    return found, reports

def ingest(client, output, item, delay=0):
    aid = item['row']['idAto']
    folder = output/str(aid)
    prior = json.loads((folder/'metadados.json').read_bytes()) if (folder/'metadados.json').exists() else None
    if prior and rfb.digest((folder/'documento.md').read_bytes()) != prior['markdown_sha256']:
        raise ValueError('Markdown em cache divergente; preservado')
    originals, views, failures, sections = [], [], [], []
    for view in ('multivigente', 'original'):
        url = f'{rfb.API}/{aid}/visao/{view}'
        try:
            path = folder/f'{view}.json'
            raw = rfb.cached(client, path, 'GET', url, delay=delay)
            data = json.loads(raw)
            if data.get('idAto') != aid or data.get('visao') not in ('multivigente', 'original', 'conjunta', 'exclusiva') or not isinstance(data.get('ementas'), list) or not isinstance(data.get('outrosSegmentos'), list):
                raise ValueError('Identidade/segmentos da fonte divergentes')
            originals.append({'arquivo': str(path.resolve()), 'source_url': url, 'sha256': rfb.digest(raw), 'bytes': len(raw)})
            text, refs, relations = rfb.render_segments(data)
            sections += [f'## Visão solicitada {view}; retornada {data["visao"]}', '', text, '']
            for bid, ref in refs.items():
                aurl = f'{rfb.API}/{aid}/anexo/{bid}'
                try:
                    embedded = ref.get('arquivoBinario')
                    binary = base64.b64decode(embedded, validate=True) if embedded else rfb.cached(client, folder/f'anexo-{bid}.bin', 'GET', aurl, delay=delay)
                    suffix = '.pdf' if binary.startswith(b'%PDF-') else ('.doc' if binary.startswith(bytes.fromhex('d0cf11e0')) else ('.jpg' if binary.startswith(b'\xff\xd8\xff') else ('.png' if binary.startswith(b'\x89PNG\r\n\x1a\n') else '.html')))
                    apath = folder/f'anexo-{bid}{suffix}'
                    if apath.exists() and apath.read_bytes() != binary:
                        raise ValueError('Anexo em cache divergente')
                    apath.write_bytes(binary)
                    if not any(o['arquivo'] == str(apath.resolve()) for o in originals):
                        originals.append({'arquivo': str(apath.resolve()), 'source_url': aurl, 'sha256': rfb.digest(binary), 'bytes': len(binary)})
                    if suffix == '.pdf':
                        pages = rfb.extract_pdf(binary)
                        sections += [f'### Anexo {bid}', '\n\n'.join(f'Página {n}\n\n{p}' for n,p in enumerate(pages,1))]
                    elif suffix == '.html':
                        encoding = 'utf-16' if binary.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
                        sections += [f'### Anexo {bid}', _convert(binary.decode(encoding), aurl)]
                    elif suffix in ('.jpg', '.png'):
                        sections += [f'### Anexo {bid}', f'![Anexo da fonte]({apath.name})', '> Imagem preservada; OCR/revisão pendente.']
                        failures.append({'anexo': bid, 'visao': view, 'erro': 'Imagem preservada; OCR pendente'})
                    else:
                        sections += [f'### Anexo {bid}', f'[Original binário preservado]({apath.name}); extração de Word legado pendente.']
                        failures.append({'anexo': bid, 'visao': view, 'erro': 'Word legado preservado; conversão pendente'})
                except Exception as exc:
                    failures.append({'anexo': bid, 'visao': view, 'erro': str(exc)})
            views.append({'visao_solicitada': view, 'visao': data['visao'], 'integro_declarado_fonte': data.get('integro'), 'historico': data.get('historico'), 'relacoes': relations, 'epigrafe': data.get('epigrafe')})
        except Exception as exc:
            failures.append({'visao': view, 'source_url': url, 'erro': str(exc)})
    if not views:
        raise ValueError(json.dumps(failures, ensure_ascii=False))
    title = item['row']['tipoAto']['siglaTipoAto']+' '+item['row']['numeroAto']+'/'+item['row']['anoAto']
    markdown = '# '+title+'\n\n> Fotografia das visões da fonte. Não inferir vigência nem datas de produção de efeitos. Revisão humana pendente.\n\n'+'\n\n'.join(sections)
    (folder/'documento.md').write_text(markdown, encoding='utf-8')
    meta = {'source_id': aid, 'source_url': originals[0]['source_url'], 'sha256': originals[0]['sha256'], 'original': Path(originals[0]['arquivo']).name, 'originais': originals, 'markdown_arquivo': 'documento.md', 'markdown_sha256': rfb.digest((folder/'documento.md').read_bytes()), 'titulo': title, 'camada': 'B' if item['row']['tipoAto'].get('idTipoAto') in (72,73) else 'A', 'tipo': 'interpretacao_administrativa' if item['row']['tipoAto'].get('idTipoAto') in (72,73) else 'legislacao', 'temas': item['temas'], 'data': item['row'].get('dataAto'), 'data_publicacao_fonte': item['row'].get('dataPublicacao'), 'vigencia': 'nao_verificada', 'revisao_humana': 'pendente', 'visoes_fonte': views, 'falhas': failures, 'status': 'parcial' if failures else 'extraido', 'coletado_em': min(json.loads(p.read_bytes())['coletado_em'] for p in folder.glob('*.receipt.json'))}
    rfb.save_json(folder/'metadados.json', meta)
    return meta

def collect(output=DEFAULT_OUTPUT, max_pages=10, delay=.1):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = {'executado_em': rfb.stamp(), 'escopo': 'Resoluções do órgão CGSN e busca literal CBS/IBS na base RFB; visões original e multivigente. Fontes externas finitas explicitadas. Não representa universalidade da legislação nem linha do tempo de vigência.', 'limites': {'max_pages_por_busca': max_pages, 'tamanho_pagina': 100}, 'coletados': 0, 'visoes': 0, 'falhas': [], 'falhas_anexos': [], 'documentos_parciais': 0, 'fontes_externas': [], 'status': 'em_andamento'}
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        found, searches = discover(client, output, delay, max_pages)
        report.update(pesquisas=searches, encontrados_unicos=len(found))
        def work(item):
            try:
                return ingest(client, output, item, delay), None
            except Exception as exc:
                return None, {'id': item['row']['idAto'], 'erro': str(exc)}
        with ThreadPoolExecutor(max_workers=3) as pool:
            for meta, error in pool.map(work, found.values()):
                if error:
                    report['falhas'].append(error)
                else:
                    report['coletados'] += 1
                    report['visoes'] += len(meta['visoes_fonte'])
                    report['documentos_parciais'] += bool(meta['falhas'])
                    report['falhas_anexos'].extend({'source_id': meta['source_id'], **e} for e in meta['falhas'])
                rfb.save_json(output/'manifesto.json', report)
        for key, url in PORTALS.items():
            try:
                folder = output/key
                raw = rfb.cached(client, folder/'original.html', 'GET', url, delay=delay)
                html = httpx.Response(200, content=raw).text
                text = _convert(html, url)
                import re
                identity = {'ec132': r'EMENDA CONSTITUCIONAL N[º°]\s*132', 'lc214': r'LEI COMPLEMENTAR N[º°]\s*214', 'lc227': r'LEI COMPLEMENTAR N[º°]\s*227', 'decreto12955': r'DECRETO N[º°]\s*12[.]955'}
                plain = ' '.join(rfb.plain(html).split())
                if key in identity and (not re.search(identity[key], plain, re.I) or not re.search(r'Art[.]\s*1', plain)):
                    raise ValueError('Identidade/conteúdo legal da página divergente')
                if len(text) < 300:
                    raise ValueError('Texto externo insuficiente')
                if (folder/'metadados.json').exists():
                    prior = json.loads((folder/'metadados.json').read_bytes())
                    if rfb.digest((folder/'documento.md').read_bytes()) != prior['markdown_sha256']:
                        raise ValueError('Markdown externo em cache divergente')
                (folder/'documento.md').write_text('# '+key+'\n\n> Vigência não verificada; fotografia da página oficial.\n\n'+text, encoding='utf-8')
                rfb.save_json(folder/'metadados.json', {'source_id': key, 'source_url': url, 'sha256': rfb.digest(raw), 'original': 'original.html', 'originais': [{'arquivo': str((folder/'original.html').resolve()), 'source_url': url, 'sha256': rfb.digest(raw), 'bytes': len(raw)}], 'markdown_arquivo': 'documento.md', 'markdown_sha256': rfb.digest((folder/'documento.md').read_bytes()), 'camada': 'A', 'tipo': 'legislacao' if key != 'marcos-reforma' else 'orientacao_oficial', 'vigencia': 'nao_verificada', 'revisao_humana': 'pendente', 'coletado_em': json.loads((folder/'original.html.receipt.json').read_bytes())['coletado_em']})
                report['fontes_externas'].append({'id': key, 'source_url': url, 'status': 'extraido'})
            except Exception as exc:
                report['fontes_externas'].append({'id': key, 'source_url': url, 'status': 'pendente', 'erro': str(exc)})
    report['status'] = 'parcial' if report['falhas'] or report['documentos_parciais'] or any(not s['completa'] for s in searches.values()) or any(s['status'] != 'extraido' for s in report['fontes_externas']) else 'coleta_concluida'
    snapshots = [json.loads(p.read_bytes()) for p in output.glob('*/metadados.json')]
    report['originais_preservados'] = sum(len(m['originais']) for m in snapshots)
    report['bytes_originais'] = sum(o['bytes'] for m in snapshots for o in m['originais'])
    rfb.save_json(output/'manifesto.json', report)
    lines = ['# Reforma CBS/IBS e histórico CGSN/MEI', '', report['escopo'], '', '[Manifesto, limites e falhas](manifesto.json)', '', f"Atos: {report['coletados']}; visões: {report['visoes']}; parciais: {report['documentos_parciais']}.", '']
    lines += [f"- [{i['row']['tipoAto']['siglaTipoAto']} {i['row']['numeroAto']}/{i['row']['anoAto']}]({aid}/documento.md)" for aid,i in found.items() if (output/str(aid)/'documento.md').exists()]
    lines += [f"- [{s['id']}]({s['id']}/documento.md)" for s in report['fontes_externas'] if s['status'] == 'extraido']
    (output/'indice.md').write_text('\n'.join(lines), encoding='utf-8')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--max-pages', type=int, default=10)
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error('--max-pages deve ser positivo')
    print(json.dumps(collect(args.output, args.max_pages), ensure_ascii=False, indent=2))
