"""Núcleo oficial IRPJ/CSLL e RIR, com a visão publicada preservada."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import httpx
from bs4 import BeautifulSoup
from .legislacao import _convert

DEFAULT_OUTPUT = Path(__file__).parent/'data'/'tributacao-lucro'
CAMARA = 'https://www2.camara.leg.br/legin/fed/'
API = 'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato'
READER = 'https://normasinternet2.receita.fazenda.gov.br/#/consulta/externa/'
SOURCES = {
 'lei9249': dict(title='Lei nº 9.249, de 26 de dezembro de 1995', url=CAMARA+'lei/1995/lei-9249-26-dezembro-1995-349062-normaatualizada-pl.html', identity=r'LEI N[º°o]?\s*9\.?249,? DE 26 DE DEZEMBRO DE 1995'),
 'lei9430': dict(title='Lei nº 9.430, de 27 de dezembro de 1996', url=CAMARA+'lei/1996/lei-9430-27-dezembro-1996-367738-normaatualizada-pl.html', identity=r'LEI N[º°o]?\s*9\.?430,? DE 27 DE DEZEMBRO DE 1996'),
 'rir9580': dict(title='Decreto nº 9.580, de 22 de novembro de 2018 — RIR', url=CAMARA+'decret/2018/decreto-9580-22-novembro-2018-787360-normaatualizada-pe.html', identity=r'DECRETO N[º°o]?\s*9\.?580,? DE 22 DE NOVEMBRO DE 2018'),
 'in1700': dict(title='Instrução Normativa RFB nº 1.700, de 14 de março de 2017', url=API+'/81268/visao/multivigente', reader_url=READER+'81268/visao/multivigente', ato=81268),
}
ARTICLE = re.compile(r'^Art\.\s*\d+(?:\.\d{3})*(?:[º°o])?(?:-[A-Z]+)?', re.I)
EPIGRAPH = re.compile(r'(?:LEI(?: COMPLEMENTAR)?|DECRETO(?:-LEI)?)\s+N[º°o]?\s*[\d.]+,?\s+DE\s+\d+\s+DE\s+\w+\s+DE\s+\d{4}', re.I)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def convert(markup, url):
    # A API usa IDs relativos para links de outros atos, não caminhos HTTP.
    soup = BeautifulSoup(markup, 'html.parser')
    for a in soup.find_all('a', href=True):
        if re.fullmatch(r'\d+(?:#.*)?', a['href']):
            aid, _, anchor = a['href'].partition('#')
            a['href'] = READER+aid+'/visao/multivigente'+('?segmento='+anchor if anchor else '')
    return _convert(str(soup), url)


def parse_html(source, raw):
    info = SOURCES[source]
    soup = BeautifulSoup(raw.decode('utf-8-sig'), 'html.parser')
    plain = ' '.join(soup.get_text(' ', strip=True).split())
    prefix = re.split(r'Art\.\s*1[º°o]?', plain, maxsplit=1, flags=re.I)[0]
    primary = EPIGRAPH.search(prefix)
    if not primary or not re.fullmatch(info['identity'], primary.group(), re.I):
        raise ValueError('Identidade primária da norma divergente')
    for block in soup.find_all('dir'):
        block.name = 'blockquote'
    articles = 0
    for block in list(soup.find_all(['p','div'])):
        if block.find(['p','div']) or block.find_parent(['table','blockquote']):
            continue
        text = ' '.join(block.get_text(' ', strip=True).split())
        match = ARTICLE.match(text)
        annex = re.match(r'^ANEXO(?:\s+[IVXLCDM]+)?$', text, re.I)
        if match or annex:
            heading = soup.new_tag('h2')
            heading.string = match.group() if match else text
            block.insert_before(heading)
            articles += bool(match)
    if not articles:
        raise ValueError('Norma sem artigos reconhecíveis')
    return convert(str(soup), info['url']), {'artigos': articles, 'tabelas': len(soup.find_all('table'))}


def parse_api(raw):
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Resposta API inválida')
    ep = data.get('epigrafe', {})
    if (data.get('idAto') != 81268 or data.get('visao') != 'multivigente' or data.get('integro') is not True
        or ep.get('numeroAto') != '1700' or ep.get('dataAto') != '2017-03-14'
        or ep.get('tipoAto',{}).get('idTipoAto') != 42
        or not any(o.get('siglaOrgao')=='RFB' for o in ep.get('orgaos',[]))):
        raise ValueError('Identidade/visão da IN RFB 1700 divergente')
    if not isinstance(data.get('ementas'),list) or not isinstance(data.get('outrosSegmentos'),list):
        raise ValueError('Segmentos ausentes')
    segments = data['ementas']+data['outrosSegmentos']
    seen, lines, articles, tables, attachments = set(), ['## Identificação publicada', '',data['epigrafeCompleta'],''], 0, 0, []
    for s in segments:
        if (not isinstance(s,dict) or type(s.get('ordemSegmentoAto')) is not int or type(s.get('idSegmento')) is not int
            or type(s.get('versaoSegmento')) is not int or not isinstance(s.get('textoIntegra'),str)):
            raise ValueError('Segmento inválido')
        key = (s['idSegmento'],s['versaoSegmento'])
        if key in seen or s.get('idAto') != 81268:
            raise ValueError('Segmento duplicado ou de outro ato')
        seen.add(key)
    for s in sorted(segments,key=lambda s:s['ordemSegmentoAto']):
        text = s['textoIntegra']
        soup = BeautifulSoup(text,'html.parser')
        match = ARTICLE.match(' '.join(soup.get_text(' ',strip=True).split()))
        articles += bool(match)
        lines += [f"## {match.group() if match else 'Segmento'} — segmento-{s['idSegmento']}-v{s['versaoSegmento']}", '']
        flags = [key for key in ('tachado','omitir','agendado') if s.get(key)]
        if flags:
            lines += ['> Marcadores literais da fonte: '+', '.join(flags)+'.','']
        lines += [convert(text,SOURCES['in1700']['reader_url']), '']
        tables += len(soup.find_all('table'))
        ref = s.get('arquivoBinario')
        if ref:
            aid = ref['idArquivoBinario']
            url = API+f'/81268/anexo/{aid}'
            attachments.append({'id':aid,'nome':ref['nomeArquivoBinario'],'source_url':url,'embutido':bool(ref.get('arquivoBinario'))})
            lines += [f"Anexo da fonte: [{ref['nomeArquivoBinario']}]({url})",'']
            if ref.get('arquivoBinario'):
                markup = base64.b64decode(ref['arquivoBinario'],validate=True).decode('utf-8-sig')
                tables += len(BeautifulSoup(markup,'html.parser').find_all('table'))
                lines += [convert(markup,url),'']
            else:
                lines += ['> Anexo externo referenciado; conteúdo não convertido nesta coleta.','']
        # Anotações históricas pertencem à versão do segmento e não são vigência inferida.
        for field in ('ancorasOrigem','ancorasDestino'):
            if s.get(field):
                lines += ['Anotações da fonte ('+field+'): '+json.dumps(s[field],ensure_ascii=False), '']
    if not articles:
        raise ValueError('IN sem artigos')
    lines += ['## Histórico publicado pela fonte','']
    for h in data.get('historico',[]):
        lines += [f"- [{h.get('texto','')}]({READER}{h['idAto']}/visao/multivigente)"]
    return '\n'.join(lines), {'artigos':articles,'segmentos':len(segments),'tabelas':tables,'anexos':attachments}


def ingest(source, raw, output=DEFAULT_OUTPUT):
    info = SOURCES[source]
    body, counts = parse_api(raw) if source=='in1700' else parse_html(source,raw)
    checksum = sha(raw)
    target = Path(output)/source/checksum
    result = target/'legislacao.md'
    original = 'original.json' if source=='in1700' else 'original.html'
    if target.exists():
        try:
            meta = json.loads((target/'metadados.json').read_bytes())
            if (meta['source_id']!=source or meta['source_url']!=info['url'] or meta['sha256']!=checksum
                or (target/original).read_bytes()!=raw or sha(result.read_bytes())!=meta['markdown_sha256']):
                raise ValueError('Cache divergente')
        except (OSError,ValueError,KeyError,TypeError) as exc:
            raise ValueError('Versão existente incompleta/corrompida; preservada') from exc
        return result
    meta = dict(source_id=source,source_url=info['url'],consulta_url=info.get('reader_url',info['url']),
        title=info['title'],publicador='Receita Federal do Brasil' if source=='in1700' else 'Câmara dos Deputados',
        coletado_em=datetime.now(timezone.utc).isoformat(),sha256=checksum,bytes=len(raw),
        visao='multivigente' if source=='in1700' else 'texto_atualizado_camara',camada='A',status='coletado',
        vigencia='nao_verificada',revisao_humana='pendente',contagens=counts)
    content = '# '+info['title']+'\n\n[Texto oficial]('+info.get('reader_url',info['url'])+') · [Original local]('+original+')\n\n> Visão publicada preservada. Vigência não verificada; revisão humana pendente.\n\n'+body+'\n'
    encoded = content.encode('utf-8')
    meta['markdown_sha256']=sha(encoded)
    meta['markdown_arquivo']='legislacao.md'
    target.mkdir(parents=True)
    (target/original).write_bytes(raw)
    result.write_bytes(encoded)
    (target/'metadados.json').write_bytes(json.dumps(meta,ensure_ascii=False,indent=2).encode('utf-8'))
    return result


def collect(output=DEFAULT_OUTPUT, client=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    records=[]
    with (httpx.Client(timeout=120,follow_redirects=True) if client is None else client) as session:
        for source,info in SOURCES.items():
            try:
                r=session.get(info['url']);r.raise_for_status()
                path=ingest(source,r.content,output)
                meta=json.loads((path.parent/'metadados.json').read_bytes())
                records.append(dict(meta,caminho=path.relative_to(output).as_posix()))
            except (httpx.HTTPError,OSError,ValueError,UnicodeError,KeyError) as exc:
                records.append(dict(source_id=source,source_url=info['url'],status='falha',erro=str(exc)))
    manifest={'total':len(records),'coletados':sum(r['status']=='coletado' for r in records),
              'falhas':sum(r['status']=='falha' for r in records),'documentos':records}
    (output/'manifesto.json').write_bytes(json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    text='# Tributação do lucro — núcleo oficial\n\nTextos da fonte, sem inferência de vigência.\n\n'
    text+='\n'.join(f"- [{r['title']}]({r['caminho']})" if r['status']=='coletado' else f"- {r['source_id']}: FALHA — {r['erro']}" for r in records)+'\n'
    (output/'indice.md').write_bytes(text.encode('utf-8'))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args();m=collect(args.output);print(json.dumps(m,ensure_ascii=False,indent=2));raise SystemExit(bool(m['falhas']))
