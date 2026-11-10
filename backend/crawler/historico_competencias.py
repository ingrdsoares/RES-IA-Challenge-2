"""Agendas federais históricas por competência e disponibilidade mensal CNPJ."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,unquote,urljoin
import httpx
from bs4 import BeautifulSoup
from defusedxml import ElementTree
from . import obrigacoes
from .paginas import ingest,normalize
from .consultas_rfb import cached,save_json,extract_pdf
from .cnpj import DAV,PUBLIC_AUTH

DATA=Path(__file__).resolve().parent/'data'
DEFAULT_OUTPUT=DATA/'historico-competencias'


def discover_months(raw,url,year):
    result={}
    body=BeautifulSoup(raw,'html.parser').select_one('#content-core')
    if body is None:return []
    parent=urlsplit(url)
    for link in body.find_all('a',href=True):
        target=urljoin(url,link['href']);parsed=urlsplit(target)
        if parsed.scheme!='https' or parsed.netloc!=parent.netloc or not parsed.path.startswith(parent.path.rstrip('/')+'/'):continue
        slug=normalize(unquote(parsed.path.rstrip('/').split('/')[-1]))
        label=normalize(link.get_text(' ',strip=True))
        for month,name in enumerate(obrigacoes.MONTHS,1):
            if slug in (name,f'{month:02d}',f'{name}-{year}',f'agenda-tributaria-{name}-{year}') and (slug!=f'{month:02d}' or name in label):
                result.setdefault(f'{year}-{month:02d}',target)
    return sorted(result.items())


def discover_pdfs(raw,url):
    body=BeautifulSoup(raw,'html.parser').select_one('#content-core')
    if body is None:return []
    result=[]
    for link in body.find_all('a',href=True):
        target=urljoin(url,link['href']).removesuffix('/view');parsed=urlsplit(target)
        if parsed.scheme=='https' and parsed.netloc=='www.gov.br' and parsed.path.startswith(urlsplit(obrigacoes.BASE).path+'/') and parsed.path.lower().endswith('.pdf') and target not in result:result.append(target)
    return result


def ingest_snapshot(sid,info,raw,output):
    digest=hashlib.sha256(raw).hexdigest();target=Path(output)/sid/digest
    mp=target/'metadados.json'
    if mp.exists():
        old=json.loads(mp.read_bytes());md=target/old.get('markdown','pagina.md')
        if old.get('markdown_sha256') and hashlib.sha256(md.read_bytes()).hexdigest()!=old['markdown_sha256']:raise ValueError('Markdown existente divergente')
    if not raw.startswith(b'%PDF-'):
        path=ingest(sid,info,raw,output);meta=json.loads(mp.read_bytes())
    elif mp.exists():
        path=target/'documento.md';meta=old
        if (target/'original.pdf').read_bytes()!=raw:raise ValueError('PDF existente divergente')
    else:
        pages=extract_pdf(raw);text='\n\n'.join(pages)
        if not all(normalize(token) in normalize(text) for token in info['identity']):raise ValueError('PDF não corresponde à identidade esperada')
        target.mkdir(parents=True,exist_ok=True);(target/'original.pdf').write_bytes(raw)
        path=target/'documento.md';path.write_text('# '+info['title']+'\n\n'+text,encoding='utf-8')
        meta=dict(source_id=sid,source_url=info['url'],sha256=digest,original='original.pdf',coletado_em=datetime.now(timezone.utc).isoformat(),status='extraido',camada='A',tipo='agenda_historica_pdf')
    meta.update(markdown_arquivo=path.name,markdown=path.name,markdown_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),original=meta.get('original','original.html'))
    save_json(mp,meta)
    return path


def collect(output=DEFAULT_OUTPUT,years=range(2018,2026),workers=3):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);records=[];errors=[];discovery=[]
    with httpx.Client(timeout=45,follow_redirects=True) as client:
        def fetch(job):
            sid,info=job
            try:
                cachepath=output/'requisicoes'/(hashlib.sha256(info['url'].encode()).hexdigest()+'.html')
                try:raw=cached(client,cachepath,'GET',info['url'],delay=.08)
                except httpx.HTTPStatusError as exc:
                    if not sid.startswith('indice-') or exc.response.status_code!=404:raise
                    info['url']=obrigacoes.BASE+'/agenda-tributaria-'+str(info['ano'])
                    cachepath=output/'requisicoes'/(hashlib.sha256(info['url'].encode()).hexdigest()+'.html')
                    raw=cached(client,cachepath,'GET',info['url'],delay=.08)
                if sid=='indice-2018' and not discover_months(raw,info['url'],2018):
                    nested=info['url']+'/agenda-tributaria-2018'
                    if nested.encode() in raw:
                        info['url']=nested
                        cachepath=output/'requisicoes'/(hashlib.sha256(nested.encode()).hexdigest()+'.html')
                        raw=cached(client,cachepath,'GET',nested,delay=.08)
                path=ingest_snapshot(sid,info,raw,output)
                meta=json.loads(path.with_name('metadados.json').read_bytes())
                return dict(meta,markdown=path.relative_to(output).as_posix()),raw,None
            except Exception as exc:return None,None,dict(source_id=sid,source_url=info['url'],status='falha',erro=str(exc))
        annualjobs=[]
        for year in years:
            url=obrigacoes.BASE+'/'+str(year)
            annualjobs.append((f'indice-{year}',dict(url=url,title=f'Agenda tributária federal {year}',identity=[str(year)],camada='A',tipo='agenda_historica',ano=year)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            annual=list(pool.map(fetch,annualjobs))
            monthlyjobs=[];pdfjobs=[]
            for (sid,info),(meta,raw,error) in zip(annualjobs,annual):
                if error:
                    errors.append(error);discovery.append(dict(ano=info['ano'],status='indice_indisponivel_ou_vazio',meses_publicados=[],meses_ausentes=[f"{info['ano']}-{m:02d}" for m in range(1,13)]));continue
                records.append(meta)
                for i,pdf in enumerate(discover_pdfs(raw,info['url'])):pdfjobs.append((f'pdf-{info["ano"]}-{i:02d}',dict(url=pdf,title=f'Agenda {info["ano"]}',identity=[str(info['ano']),'agenda'],camada='A')))
                months=discover_months(raw,info['url'],info['ano'])
                discovery.append(dict(ano=info['ano'],pdfs_publicados=len(discover_pdfs(raw,info['url'])),status='indice_vazio' if not months and not discover_pdfs(raw,info['url']) else 'publicado',meses_publicados=[p for p,u in months],meses_ausentes=[f"{info['ano']}-{m:02d}" for m in range(1,13) if f"{info['ano']}-{m:02d}" not in {p for p,u in months}]))
                for period,url in months:
                    monthlyjobs.append(('mes-'+period,dict(url=url,title='Agenda '+period,identity=[str(info['ano'])],camada='A',tipo='agenda_mensal_historica',periodo=period)))
            # The 2024 annual HTML index is empty; its official PDF collection is separate.
            for archive_year in (2019,2024):
                if archive_year not in years:continue
                url=obrigacoes.BASE+'/arquivos-e-imagens-agenda-tributaria/agenda-tributaria-'+str(archive_year)+('-1' if archive_year==2024 else '')
                info=dict(url=url,title=f'PDFs agenda {archive_year}',identity=[str(archive_year)],ano=archive_year,camada='A')
                meta,raw,error=fetch((f'indice-pdfs-{archive_year}',info))
                if error:errors.append(error)
                else:
                    records.append(meta)
                    for item in discovery:
                        if item['ano']==archive_year:item['pdfs_publicados']=len(discover_pdfs(raw,url))
                    for i,pdf in enumerate(discover_pdfs(raw,url)):pdfjobs.append((f'pdf-{archive_year}-colecao-{i:02d}',dict(url=pdf,title=f'Agenda {archive_year}',identity=[str(archive_year),'agenda'],camada='A')))
            monthly=list(pool.map(fetch,monthlyjobs));dailyjobs=[]
            for (sid,info),(meta,raw,error) in zip(monthlyjobs,monthly):
                if error:errors.append(error);continue
                records.append(meta)
                pdfs=discover_pdfs(raw,info['url'])
                for i,pdf in enumerate(pdfs):pdfjobs.append((sid+f'-pdf-{i:02d}',dict(url=pdf,title=info['title'],identity=[info['periodo'][:4],'agenda'],camada='A')))
                try:days=obrigacoes.discover_days(raw,info['url'],info['periodo'])
                except ValueError as exc:
                    if not pdfs:errors.append(dict(source_url=info['url'],status='falha',erro=str(exc)))
                    continue
                for i,url in enumerate(days):
                    match=re.search(r'dia-(\d{2})-(\d{2})-(\d{4})$',url)
                    identity=[f'{match[1]}/{match[2]}/{match[3]}'] if match else (['diario'] if url.rstrip('/').endswith('/diario') else ['vencimentos'])
                    dailyjobs.append((info['periodo']+f'-dia-{i:02d}',dict(url=url,title='Vencimentos '+info['periodo'],identity=identity,camada='A',tipo='agenda_diaria_historica',periodo=info['periodo'])))
            for meta,raw,error in pool.map(fetch,dailyjobs+pdfjobs):
                if error:errors.append(error)
                else:records.append(meta)
    # The public listing documents availability; it is not a historical cadastral snapshot.
    cnpj={}
    try:
        with httpx.Client(timeout=90,auth=PUBLIC_AUTH,follow_redirects=True) as client:
            r=client.request('PROPFIND',DAV,headers={'Depth':'1'});r.raise_for_status();raw=r.content
        tree=ElementTree.fromstring(raw,forbid_dtd=True,forbid_entities=True,forbid_external=True)
        months=[]
        for node in tree.findall('{DAV:}response'):
            name=unquote(urlsplit(node.findtext('{DAV:}href','')).path).rstrip('/').split('/')[-1]
            if re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])',name):months.append(name)
        if not months:raise ValueError('Listagem sem competências CNPJ')
        sha=hashlib.sha256(raw).hexdigest();target=output/'disponibilidade-cnpj'/sha;target.mkdir(parents=True,exist_ok=True)
        original=target/'original.xml';md=target/'documento.md'
        text='# Competências CNPJ publicadas\n\nSomente disponibilidade no compartilhamento público; os dados cadastrais destes meses não foram baixados nesta frente.\n\n'+'\n'.join('- '+m for m in sorted(set(months)))+'\n'
        mp=target/'metadados.json'
        if mp.exists():
            old=json.loads(mp.read_bytes())
            if original.read_bytes()!=raw or hashlib.sha256(md.read_bytes()).hexdigest()!=old['markdown_sha256']:raise ValueError('Cache CNPJ divergente')
        else:
            original.write_bytes(raw);md.write_bytes(text.encode());save_json(mp,dict(source_id='disponibilidade-cnpj',source_url=DAV,sha256=sha,coletado_em=datetime.now(timezone.utc).isoformat(),original='original.xml',markdown_sha256=hashlib.sha256(md.read_bytes()).hexdigest(),status='coletado',tipo='catalogo_disponibilidade',camada='A',competencias=sorted(set(months)),revisao_humana='pendente'))
        cnpj=dict(competencias=sorted(set(months)),markdown=md.relative_to(output).as_posix(),limite='Não são snapshots cadastrais baixados')
    except Exception as exc:errors.append(dict(source_url=DAV,status='falha',erro=str(exc)))
    report=dict(executado_em=datetime.now(timezone.utc).isoformat(),anos=list(years),workers=workers,coletados=len(records),descoberta=discovery,
        documentos=records,disponibilidade_cnpj=cnpj,falhas=errors,status='parcial' if errors else 'coleta_concluida',limites='Agendas publicadas 2018–2025; não certifica vigência atual, exigibilidade ou adiamento de prazo. Listagem CNPJ apenas informa competências disponíveis, sem inventar dados antigos.')
    report['cobertura_por_ano']={str(year):dict(documentos=sum(1 for r in records if str(year) in r['source_id']),pdfs=sum(1 for r in records if str(year) in r['source_id'] and r.get('original')=='original.pdf')) for year in years}
    for item in discovery:
        item['pdfs_coletados']=report['cobertura_por_ano'][str(item['ano'])]['pdfs']
        item['status']='html_mensal_publicado' if item['meses_publicados'] else ('pdfs_publicados' if item['pdfs_coletados'] else 'indice_vazio')
    save_json(output/'manifesto.json',report)
    text='# Histórico por competência\n\n'+report['limites']+'\n\nDocumentos de agenda: '+str(len(records))+'.\n\n'
    text+='\n'.join('- ['+str(r.get('title',r['source_id']))+']('+r['markdown']+')' for r in records)+'\n'
    if cnpj:text+='\n[Disponibilidade mensal CNPJ]('+cnpj['markdown']+')\n'
    (output/'indice.md').write_bytes(text.encode());return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workers',type=int,choices=(1,2,3),default=3);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);args=p.parse_args()
    m=collect(args.output,workers=args.workers);print(json.dumps({k:m[k] for k in ('coletados','descoberta','falhas')},ensure_ascii=False,indent=2))
