"""Acervo temático oficial SC/SD: originais, ementas e integrais disponíveis."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import time
import threading

from bs4 import BeautifulSoup
import httpx
from markdownify import markdownify
import pypdfium2

PDF_LOCK = threading.Lock()

SEARCH = 'https://normas.receita.fazenda.gov.br/api/indexacao/ato/pesquisar'
API = 'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato'
ACERVO = 'https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/legislacao/solucoes-de-consultas-e-de-divergencias'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'consultas-rfb'
TERMS = {'simples-nacional': '"Simples Nacional"', 'mei': '"microempreendedor individual" OR MEI OR SIMEI', 'fator-r': '"fator R"', 'fator-busca-ampla': 'fator', 'segregacao-receitas': 'segregação AND receita'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def request(client, method, url, *, payload=None, delay=.15):
    for attempt in range(3):
        time.sleep(delay * (2 ** attempt))
        try:
            r = client.request(method, url, json=payload) if payload is not None else client.request(method, url)
            r.raise_for_status()
            return r.content
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            if attempt == 2:
                raise


def cached(client, path, method, url, *, payload=None, delay=.15):
    receipt = path.with_suffix(path.suffix + '.receipt.json')
    if path.exists():
        raw = path.read_bytes()
        meta = json.loads(receipt.read_text(encoding='utf-8'))
        if digest(raw) != meta['sha256'] or meta['source_url'] != url or meta.get('request') != payload:
            raise ValueError(f'Cache divergente: {path}')
        return raw
    raw = request(client, method, url, payload=payload, delay=delay)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    save_json(receipt, {'source_url': url, 'request': payload, 'sha256': digest(raw), 'coletado_em': stamp()})
    return raw


def search_payload(term, page, size=100):
    return dict(tipoPesquisa='formulario', termo=term, tiposAtosSelecionados='72;73', internet=True,
        publicado=True, apenasAtosVigentes=False, apenasAtosInternos=False, tipoData='dataPublicacao',
        paginacaoPaginaAtual=page, paginacaoQuantidadePorPagina=size, ordenacaoColuna='publicacao',
        ordenacaoDirecao='desc', refino={})


def parse_page(raw):
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not isinstance(obj.get('atos'), list) or type(obj.get('quantidadeTotal')) is not int or type(obj.get('quantidadePaginas')) is not int:
        raise ValueError('Listagem sem atos/total/paginação válidos')
    for row in obj['atos']:
        if type(row.get('idAto')) is not int or row.get('tipoAto', {}).get('idTipoAto') not in (72, 73):
            raise ValueError('Listagem retornou ato fora dos tipos SC/SD')
    return obj


def discover(client, output, *, delay=.15, max_pages=None):
    found, report = {}, {}
    for theme, term in TERMS.items():
        ids, page, total, pages = set(), 1, None, None
        while True:
            raw = cached(client, output / 'listagens' / theme / f'{page:04}.json', 'POST', SEARCH,
                payload=search_payload(term, page), delay=delay)
            data = parse_page(raw)
            if total is not None and (total != data['quantidadeTotal'] or pages != data['quantidadePaginas']):
                raise ValueError('Total da pesquisa mudou durante paginação; atualizar listagens')
            total, pages = data['quantidadeTotal'], data['quantidadePaginas']
            new_ids = {r['idAto'] for r in data['atos']}
            if ids.intersection(new_ids) or len(new_ids) != len(data['atos']):
                raise ValueError('IDs repetidos na paginação; não alegar cobertura completa')
            ids.update(new_ids)
            for row in data['atos']:
                item = found.setdefault(row['idAto'], {'row': row, 'temas': []})
                item['temas'].append(theme)
            report[theme] = {'termo': term, 'total_fonte': total, 'paginas_fonte': pages,
                'paginas_coletadas': page, 'encontrados': len(ids), 'completa': len(ids) == total}
            save_json(output / 'descoberta.json', {'pesquisas': report, 'unicos': len(found), 'atualizado_em': stamp()})
            if page >= pages or (max_pages and page >= max_pages):
                break
            if not data['atos']:
                raise ValueError('Página vazia antes do término')
            page += 1
        if not max_pages and len(ids) != total:
            raise ValueError('Contagem não confere com total declarado')
    return found, report


def parse_detail(raw, aid):
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Detalhe inválido')
    if data.get('idAto') != aid or (data.get('visao') not in ('multivigente', 'original') and not (data.get('visao') == 'exclusiva' and data.get('ehVisaoExclusiva') is True)) or not isinstance(data.get('ementas'), list) or not isinstance(data.get('outrosSegmentos'), list):
        raise ValueError('Detalhe não corresponde ao ato solicitado')
    return data


def plain(html):
    return BeautifulSoup(html or '', 'html.parser').get_text(' ', strip=True)


def render_segments(data):
    lines, attachments, relations = [], {}, []
    for segment in sorted(data['ementas'] + data['outrosSegmentos'], key=lambda s: s['ordemSegmentoAto']):
        text = segment.get('textoIntegra') or ''
        flags = [k for k in ('tachado', 'omitir', 'agendado') if segment.get(k)]
        lines += [f"## Segmento {segment['idSegmento']} — versão {segment.get('versaoSegmento')}", '']
        if flags:
            lines += ['> Marcadores da fonte: ' + ', '.join(flags), '']
        lines += [markdownify(text, heading_style='ATX').strip(), '']
        if segment.get('arquivoBinario'):
            ref = segment['arquivoBinario']
            attachments[ref['idArquivoBinario']] = ref
        relations.append({k: segment.get(k) for k in ('idSegmento', 'versaoSegmento', 'ancorasOrigem', 'ancorasDestino')})
    return '\n'.join(lines), attachments, relations


def extract_pdf(raw):
    if not raw.startswith(b'%PDF-'):
        raise ValueError('Anexo não é PDF')
    pages = []
    # PDFium possui estado global; serializar evita acesso concorrente inseguro.
    with PDF_LOCK:
        doc = pypdfium2.PdfDocument(raw)
        try:
            for i in range(len(doc)):
                page = doc[i]
                try:
                    text = page.get_textpage()
                    try:
                        pages.append(text.get_text_bounded().replace('\r\n', '\n'))
                    finally:
                        text.close()
                finally:
                    page.close()
        finally:
            doc.close()
    if not pages:
        raise ValueError('PDF sem páginas')
    return pages


def ingest(client, output, item, *, delay=.15):
    row, themes = item['row'], item['temas']
    aid = row['idAto']
    folder = output / str(aid)
    url = f'{API}/{aid}/visao/multivigente'
    receipt = folder / 'original.json.receipt.json'
    if receipt.exists():
        url = json.loads(receipt.read_text(encoding='utf-8'))['source_url']
    try:
        raw = cached(client, folder / 'original.json', 'GET', url, delay=delay)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 406:
            raise
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'visao-indisponivel.json').write_bytes(exc.response.content)
        save_json(folder / 'visao-indisponivel.json.receipt.json', {'source_url': url, 'status_http': 406, 'sha256': digest(exc.response.content), 'coletado_em': stamp()})
        url = f'{API}/{aid}/visao/original'
        raw = cached(client, folder / 'original.json', 'GET', url, delay=delay)
    data = parse_detail(raw, aid)
    text, refs, relations = render_segments(data)
    attachments, failures, pdf_texts = [], [], []
    for bid, ref in refs.items():
        aurl = f'{API}/{aid}/anexo/{bid}'
        try:
            pdf = cached(client, folder / f'{bid}.pdf', 'GET', aurl, delay=delay)
            extracted = folder / f'{bid}.pages.json'
            if extracted.exists():
                saved = json.loads(extracted.read_text(encoding='utf-8'))
                if saved['source_sha256'] != digest(pdf) or saved['texto_sha256'] != digest(json.dumps(saved['paginas'], ensure_ascii=False).encode('utf-8')):
                    raise ValueError('Extração PDF em cache divergente')
                pages = saved['paginas']
                extractor = saved.get('extrator', 'pdfplumber')
                extractor_version = saved.get('versao_extrator', 'nao_registrada')
            else:
                pages = extract_pdf(pdf)
                extractor, extractor_version = 'pypdfium2', version('pypdfium2')
                save_json(extracted, {'source_sha256': digest(pdf), 'extrator': extractor, 'versao_extrator': extractor_version, 'paginas': pages, 'texto_sha256': digest(json.dumps(pages, ensure_ascii=False).encode('utf-8'))})
            review_path = folder / 'revisao-paginas.json'
            reviews = json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
            review = reviews.get(str(bid), {})
            blanks = review.get('paginas_em_branco', []) if review.get('source_sha256') == digest(pdf) else []
            missing_pages = [n for n,t in enumerate(pages,1) if not t.strip()]
            blanks = [n for n in blanks if n in missing_pages]
            attachments.append({'id': bid, 'paginas_em_branco_verificadas': blanks, 'paginas_ocr_pendente': [n for n in missing_pages if n not in blanks], 'verificacao_paginas': review if blanks else None, 'extrator': extractor, 'versao_extrator': extractor_version, 'nome': ref['nomeArquivoBinario'], 'source_url': aurl,
                'arquivo': str((folder / f'{bid}.pdf').resolve()), 'bytes': len(pdf), 'sha256': digest(pdf), 'paginas': len(pages), 'paginas_sem_texto': [n for n,t in enumerate(pages,1) if not t.strip()]})
            for n, p in enumerate(pages, 1):
                pdf_texts.extend([f'## Anexo {bid} — página {n}', '', p if p.strip() else ('> Página em branco, conferida visualmente no PDF original.' if n in blanks else '> Página sem texto extraível; conferir PDF e necessidade de OCR.'), ''])
        except Exception as exc:
            failures.append({'id': bid, 'source_url': aurl, 'erro': str(exc)})
    ep = data['epigrafe']
    meta = {'source_url': url, 'source_id': aid, 'coletado_em': json.loads((folder / 'original.json.receipt.json').read_text(encoding='utf-8'))['coletado_em'],
        'sha256': digest(raw), 'originais': [{'arquivo': str((folder / 'original.json').resolve()), 'source_url': url, 'sha256': digest(raw), 'bytes': len(raw)}] + [{'arquivo': a['arquivo'], 'source_url': a['source_url'], 'sha256': a['sha256'], 'bytes': a['bytes']} for a in attachments], 'camada': 'B', 'tipo': 'interpretacao_administrativa', 'orgao': ep['orgaos'],
        'numero': ep['numeroAto'], 'data': ep['dataAto'], 'tipo_ato': ep['tipoAto'], 'assunto': plain(row.get('ementa')),
        'vigencia': 'nao_verificada', 'revisao_humana': 'pendente', 'temas': themes,
        'status': 'anexos_pendentes' if failures else ('ocr_pendente' if any(a['paginas_ocr_pendente'] for a in attachments) else 'extraido'),
        'conteudo': 'ementa_e_anexos' if attachments else 'ementa_e_segmentos_disponiveis',
        'visao_fonte': data['visao'], 'integro_declarado_fonte': data.get('integro'), 'texto_integral_verificado': False,
        'relacoes_fonte': relations, 'historico_fonte': data.get('historico'), 'anexos': attachments, 'falhas_anexos': failures}
    markdown = f'---\ncamada: B\ntipo: interpretacao_administrativa\nsource_id: {aid}\nsource_url: {url}\nsha256: {digest(raw)}\nvigencia: nao_verificada\nrevisao_humana: pendente\n---\n\n# ' + data['epigrafeCompleta'] + '\n\n> Interpretação administrativa. Ementa e segmentos da fonte; o campo integro da API não comprova a disponibilidade do texto integral. Anexos, quando disponíveis, seguem abaixo. Revisão humana pendente.\n\n' + text
    for attachment in attachments:
        markdown += f"\n[PDF original {attachment['id']}]({attachment['id']}.pdf)\n"
    if pdf_texts:
        markdown += '\n\n# Texto dos anexos PDF\n\n' + '\n'.join(pdf_texts)
    (folder / 'documento.md').write_text(markdown, encoding='utf-8')
    meta['markdown_sha256'] = digest((folder / 'documento.md').read_bytes())
    save_json(folder / 'metadados.json', meta)
    return meta


def collect(output=DEFAULT_OUTPUT, *, delay=.15, workers=3, max_pages=None, max_documents=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        cached(client, output / 'acervo.html', 'GET', ACERVO, delay=delay)
        types = json.loads(cached(client, output / 'tipos-atos.json', 'GET', 'https://normas.receita.fazenda.gov.br/api/tipoAto/ativo', delay=delay))
        if {x['idTipoAto']: x['siglaTipoAto'] for x in types if x['idTipoAto'] in (72,73)} != {72: 'SC', 73: 'SD'}:
            raise ValueError('Tipos SC/SD não conferem com catálogo oficial')
        found, searches = discover(client, output, delay=delay, max_pages=max_pages)
        items = list(found.values())[:max_documents]
        manifest = {'source_url': ACERVO, 'pesquisa_url': SEARCH, 'escopo': 'Corte temático SC/SD; não é acervo universal. Temas recuperados por busca textual da fonte, sem inferir pertinência.',
            'executado_em': stamp(), 'snapshot': 'Cache fechado desta execução; para nova fotografia preservar esta pasta e usar --output com destino novo datado.',
            'limites': {'max_pages': max_pages, 'max_documents': max_documents}, 'pesquisas': searches,
            'encontrados_unicos': len(found), 'ocorrencias': sum(x['encontrados'] for x in searches.values()),
            'deduplicados': sum(x['encontrados'] for x in searches.values()) - len(found),
            'coletados': 0, 'ementas': 0, 'documentos_com_anexos': 0, 'documentos_ocr_pendente': 0, 'paginas_sem_texto': 0, 'paginas_ocr_pendente': 0, 'paginas_em_branco_verificadas': 0, 'falhas': [], 'falhas_anexos': [], 'status': 'em_andamento'}
        def work(item):
            try:
                return item['row']['idAto'], ingest(client, output, item, delay=delay), None
            except Exception as exc:
                return item['row']['idAto'], None, str(exc)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for aid, meta, error in pool.map(work, items):
                if error:
                    manifest['falhas'].append({'source_id': aid, 'erro': error})
                else:
                    manifest['coletados'] += 1
                    manifest['ementas'] += 1
                    manifest['documentos_com_anexos'] += bool(meta['anexos'])
                    missing = sum(len(a['paginas_sem_texto']) for a in meta['anexos'])
                    manifest['paginas_sem_texto'] += missing
                    ocr = sum(len(a['paginas_ocr_pendente']) for a in meta['anexos'])
                    manifest['paginas_ocr_pendente'] += ocr
                    manifest['paginas_em_branco_verificadas'] += sum(len(a['paginas_em_branco_verificadas']) for a in meta['anexos'])
                    manifest['documentos_ocr_pendente'] += bool(ocr)
                    manifest['falhas_anexos'].extend({'source_id': aid, **f} for f in meta['falhas_anexos'])
                manifest['atualizado_em'] = stamp()
                save_json(output / 'manifesto.json', manifest)
        manifest['status'] = 'coleta_concluida' if not manifest['falhas'] and not manifest['falhas_anexos'] and len(items) == len(found) and all(x['completa'] for x in searches.values()) else 'parcial'
        save_json(output / 'manifesto.json', manifest)
        lines = ['# Soluções de Consulta e Divergência — recorte temático', '', 'Camada B. Interpretação administrativa; vigência não verificada e revisão humana pendente.', '', f"Encontrados únicos: {len(found)}. Coletados: {manifest['coletados']}. Status: {manifest['status']}.", '', '[Manifesto e limites](manifesto.json)', '', f"Documentos com OCR pendente: {manifest['documentos_ocr_pendente']}; páginas: {manifest['paginas_sem_texto']}. Páginas sem texto podem estar em branco ou exigir OCR; revisão pendente.", '']
        for theme, search in searches.items():
            lines += [f"## {theme} — {search['encontrados']} / {search['total_fonte']} resultados", '']
            for item in found.values():
                if theme not in item['temas']:
                    continue
                row = item['row']
                label = row['tipoAto']['siglaTipoAto'] + ' ' + '/'.join(o['siglaOrgao'] for o in row.get('orgaos', [])) + ' ' + row['numeroAto'] + '/' + row['anoAto']
                lines.append(f"- [{label}]({row['idAto']}/documento.md) — fonte ID {row['idAto']}" if (output / str(row['idAto']) / 'documento.md').exists() else f"- {label} — pendente, ID {row['idAto']}")
            lines.append('')
        (output / 'indice.md').write_text('\n'.join(lines), encoding='utf-8')
        return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    p.add_argument('--delay', type=float, default=.15)
    p.add_argument('--workers', type=int, choices=(1,2,3), default=3)
    p.add_argument('--max-pages', type=int)
    p.add_argument('--max-documents', type=int)
    args = p.parse_args()
    if args.delay < 0 or any(x is not None and x <= 0 for x in (args.max_pages,args.max_documents)):
        p.error('Limites positivos; intervalo não negativo')
    result = collect(args.output, delay=args.delay, workers=args.workers, max_pages=args.max_pages, max_documents=args.max_documents)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['status'] != 'coleta_concluida':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
