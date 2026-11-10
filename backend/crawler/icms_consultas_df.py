"""Corpus ICMS DF: grafo oficial limitado e páginas públicas de consultas no DODF."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urldefrag
import httpx
import pypdfium2
from bs4 import BeautifulSoup
from .distrital_df import _ssl_context, normalize
from .legislacao import _convert

DEFAULT_OUTPUT=Path(__file__).parent/'data'/'icms-consultas-df'
BASE='https://www.sinj.df.gov.br'
SEEDS=[BASE+'/sinj/Norma/49208/Lei_1254_08_11_1996.html',BASE+'/sinj/Norma/33077/exec_dec_18955_1997_rep_ret.html']
DIARIES=['ee93a046-3083-32fc-abd3-05177b34c172','f0394794-d80e-3300-9566-4bdf1b7f6454','b4deb402-ad96-3a80-a43b-63db29ea3c88','672a955e-2979-353b-8422-e7e737c4739e','1b081b1b-3655-3239-8286-f6206dd4d08c']

def canonical(url):
    url=urldefrag(url)[0]
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname!='www.sinj.df.gov.br':return None
    if not (re.match(r'^/sinj/Norma/[^/]+/[^/]+\.(?:html?|pdf)$',p.path,re.I) or p.path=='/sinj/TextoArquivoDiario.aspx'):return None
    return url

def discover(raw,url):
    soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser')
    return sorted({u for a in soup.select('a[href]') if (u:=canonical(urljoin(url,a['href'])))})

def classify_diary(text):
    plain=normalize(text)
    heading=r'(?:solucao de consulta|declaracao de (?:ineficacia|inadmissibilidade) de consulta) n(?:o)? \d+ \d{4}'
    for match in re.finditer(heading,plain):
        context=plain[match.start():match.end()+700]
        if re.search(r'\bicms\b|tributari|lei (?:no )?4 567|lei kandir',context):
            return 'diario_com_consulta_tributaria'
    if 'icms' in plain and ('acordao' in plain or 'tribunal administrativo de recursos fiscais' in plain):
        return 'diario_com_jurisprudencia_tributaria'
    return 'diario_geral'

def parse(raw,url):
    if raw.startswith(b'%PDF-'):
        expected={'31519':'18107','32566':'18670','32661':'18726','32685':'18740'}
        key=urlsplit(url).path.split('/')[3]
        with pypdfium2.PdfDocument(raw) as doc:
            pages=[]
            for i in range(len(doc)):
                page=doc[i];text=page.get_textpage();pages.append(text.get_text_range());text.close();page.close()
        prefix=' '.join(pages)[:2000]
        match=re.search(r'DECRETO\s+N[º°o]?\.?\s*(\d[\d.]*)',prefix,re.I)
        if not match or match[1].replace('.','')!=expected.get(key):raise ValueError('Identidade PDF divergente')
        if not all(x.strip() for x in pages):raise ValueError('PDF contém páginas sem texto; OCR necessário')
        return 'Decreto '+match[1], '\n\n'.join(f'## Página {i}\n\n'+text for i,text in enumerate(pages,1)),dict(paginas=len(pages),tipo='legislacao_pdf',caracteres=sum(map(len,pages)),extrator='pypdfium2',tabelas='conferir_original')
    markup=re.sub(r'(?i)(<p(?:\s[^>]*|)>)',r'</p>\1',raw.decode('utf-8-sig'))
    soup=BeautifulSoup(markup,'html.parser')
    diary='/TextoArquivoDiario.aspx' in url
    body=soup.select_one('#div_texto') if not diary else soup.body
    if body is None:raise ValueError('Bloco documental SINJ ausente')
    title=soup.find('h1') if not diary else soup.title
    title=title.get_text(' ',strip=True) if title else ''
    if not title and not diary:
        header=re.search(r'PORTARIA\s+N[º°o]?\s*42\s+DE\s+07\s+DE\s+MARÇO\s+DE\s+2016',body.get_text(' ',strip=True),re.I)
        if header:title=header[0]
    plain=body.get_text(' ',strip=True)
    if diary:
        if 'icms' not in normalize(plain) or len(plain)<1000:raise ValueError('Diário sem conteúdo ICMS identificável')
    elif not title or not re.search(r'Art\.?\s*\d|ANEXO',plain,re.I) or len(plain)<150:raise ValueError('Norma sem identidade/dispositivos')
    # Identity is tied to SINJ page title and h1; reject generic portals/errors.
    if not diary:
        page_title=soup.title.get_text(' ',strip=True) if soup.title else ''
        heading_number=re.search(r'\d[\d.]*',title)
        page_number=re.search(r'\d[\d.]*',page_title)
        if not heading_number or not page_number or int(heading_number[0].replace('.',''))!=int(page_number[0].replace('.','')) or normalize(title).split()[0]!=normalize(page_title).split()[0]:raise ValueError('Título e cabeçalho divergentes')
    for n in body.select('script,style,nav,footer'):n.decompose()
    for n in body.select('.strike'):n.name='del'
    return title,_convert(str(body),url),dict(tabelas=len(body.find_all('table')),anexos=len(re.findall(r'\bANEXO\b',plain,re.I)),tipo=classify_diary(plain) if diary else 'legislacao',caracteres=len(plain))

def ingest(raw,url,output):
    url=canonical(url)
    if not url:raise ValueError('URL fora da fronteira oficial')
    title,body,stats=parse(raw,url)
    if url in SEEDS:
        number=re.search(r'\d[\d.]*',title)
        if not number or number[0].replace('.','')!=('1254' if url==SEEDS[0] else '18955'):raise ValueError('Identidade da norma semente divergente')
    digest=hashlib.sha256(raw).hexdigest();sid='sinj-'+hashlib.sha256(url.encode()).hexdigest()[:20]
    target=Path(output)/sid/digest; md=target/'documento.md';original='original.pdf' if raw.startswith(b'%PDF-') else 'original.html'
    if target.exists():
        meta=json.loads((target/'metadados.json').read_bytes())
        if meta.get('source_url')!=url or (target/original).read_bytes()!=raw or hashlib.sha256(md.read_bytes()).hexdigest()!=meta.get('markdown_sha256'):raise ValueError('Cache incompleto/divergente')
        return dict(meta,markdown=md.relative_to(output).as_posix())
    text=f'# {title}\n\n[Original]({original}) · [Fonte oficial]({url})\n\n> Vigência e aplicabilidade não verificadas. Revisão humana pendente. Diários são páginas integrais, não pareceres individualizados.\n\n{body}\n'
    meta=dict(source_id=sid,source_url=url,titulo=title,sha256=digest,original=original,markdown_arquivo='documento.md',markdown_sha256=hashlib.sha256(text.encode()).hexdigest(),coletado_em=datetime.now(timezone.utc).isoformat(),status='extraido',camada='A',jurisdicao='Distrito Federal',vigencia='nao_verificada',revisao_humana='pendente',**stats)
    target.mkdir(parents=True);(target/original).write_bytes(raw);md.write_bytes(text.encode());(target/'metadados.json').write_bytes(json.dumps(meta,ensure_ascii=False,indent=2).encode())
    return dict(meta,markdown=md.relative_to(output).as_posix())

def collect(output=DEFAULT_OUTPUT,limit=200,client=None):
    if not 2<=limit<=1000:raise ValueError('Limite deve estar entre 2 e 1000')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    session=client or httpx.Client(timeout=60,follow_redirects=True,verify=_ssl_context())
    records=[];discovery=[];queue=list(SEEDS);seen=set();links=set()
    def fetch(url):
        try:
            response=session.get(url);response.raise_for_status()
            if not canonical(str(response.url)):raise ValueError('Redirecionamento fora da fronteira')
            return response.content,None
        except Exception as exc:return None,str(exc)
    # Only seed documents expand: finite one-hop graph, not a site-wide crawl.
    for url in SEEDS:
        raw,error=fetch(url);seen.add(url)
        if raw is not None:
            found=discover(raw,url);links.update(found)
            discovery.append(dict(source_url=url,links=found,total=len(found)))
            try:records.append(ingest(raw,url,output))
            except (ValueError,OSError,UnicodeError) as exc:records.append(dict(source_url=url,status='erro',erro=str(exc)))
        else:records.append(dict(source_url=url,status='erro',erro=error))
    candidates=sorted(links-seen)
    # Include all discovered document formats within the explicit bound.
    candidates=candidates[:limit-2]
    candidates += [BASE+'/sinj/TextoArquivoDiario.aspx?id_file='+i for i in DIARIES]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for url,(raw,error) in zip(candidates,pool.map(fetch,candidates)):
            try:
                if error:raise ValueError(error)
                records.append(ingest(raw,url,output))
            except (ValueError,OSError,UnicodeError) as exc:records.append(dict(source_url=url,status='erro',erro=str(exc)))
            print(len(records),records[-1]['status'],url,flush=True)
    if client is None:session.close()
    report=dict(total=len(records),extraidos=sum(r['status']=='extraido' for r in records),falhas=sum(r['status']=='erro' for r in records),limite_normas=limit,descobertos=len(links),descoberta=discovery,documentos=records,limitacoes=['Grafo de um salto a partir da Lei 1254 e Decreto 18955; ordem URL determinística e limite explícito.','Anexos incorporados preservados no texto integral. URLs terminadas em PDF podem servir HTML; formato detectado nos bytes. PDFs reais usam PDFium e exigem revisão de tabelas.','Diários: quatro páginas contendo consultas tributárias e uma contendo jurisprudência TARF, localizadas por pesquisa; não constitui coleção exaustiva ou paginação de catálogo de consultas.','Não consolida alterações nem determina vigência.'])
    if (output/'manifesto.json').exists():
        previous=(output/'manifesto.json').read_bytes();history=output/'historico';history.mkdir(exist_ok=True);(history/(hashlib.sha256(previous).hexdigest()+'.json')).write_bytes(previous)
    (output/'manifesto.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode())
    (output/'indice.md').write_bytes(('# ICMS e consultas — DF\n\n'+ '\n'.join('- '+x for x in report['limitacoes'])+'\n\n'+'\n'.join(f'- [{r["titulo"]}]({r["markdown"]})' if r['status']=='extraido' else f'- ERRO {r["source_url"]}: {r["erro"]}' for r in records)+'\n').encode())
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);p.add_argument('--limit',type=int,default=200);a=p.parse_args();r=collect(a.output,a.limit);print(json.dumps({k:r[k] for k in ('total','extraidos','falhas','descobertos')},ensure_ascii=False))
