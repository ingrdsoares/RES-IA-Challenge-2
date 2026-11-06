"""Bounded public Receita DF annual consultations and paginated TARF decisions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlsplit, parse_qs
import httpx
from bs4 import BeautifulSoup
from .distrital_df import _ssl_context, normalize
from .legislacao import _convert

DEFAULT_OUTPUT=Path(__file__).parent/'data'/'consultas-df-amplas'
API='https://ww1.receita.fazenda.df.gov.br/WPI/api/informacoes-tributarias/informacoes-tributarias-consulta'
CATALOG='https://ww1.receita.fazenda.df.gov.br/informacoes-tributarias/informacoes-tributarias-consulta'
TARF='https://www.receita.fazenda.df.gov.br/aplicacoes/tarf/'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def save_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def decode(raw):
    try:return raw.decode('utf-8-sig')
    except UnicodeDecodeError:return raw.decode('cp1252',errors='replace')
def relevant(text):return bool(re.search(r'\b(?:icms|iss|issqn)\b|simples nacional',normalize(text)))
def tarf_links(raw):
    soup=BeautifulSoup(decode(raw),'html.parser');links=set()
    for a in soup.select('a[href]'):
        p=urlsplit(a['href'])
        if p.path.lower().endswith('/telasaidaacordao.cfm'):
            q=parse_qs(p.query)
            if all(k in q for k in ('Camara','Acordao','AnoAcordao')):
                links.add(TARF+'TelaSaidaAcordao.cfm?'+urlencode({k:q[k][0] for k in ('Camara','Acordao','AnoAcordao')}))
    return sorted(links)
def ingest(raw,url,output,kind,extra=None):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ('ww1.receita.fazenda.df.gov.br','www.receita.fazenda.df.gov.br'):raise ValueError('URL fora da origem oficial')
    soup=BeautifulSoup(decode(raw),'html.parser')
    for node in soup.select('script,style,nav,header,footer'):node.decompose()
    if kind=='jurisprudencia_tarf':
        plain=soup.get_text(' ',strip=True)
        if not all(x in normalize(plain) for x in ['ementa','decisao','acordao']):raise ValueError('TARF sem ementa/decisão')
        # Public endpoint supplies ementa and disposition, not the full judicial vote.
        title='TARF — '+urlsplit(url).query
    else:
        title=(extra or {}).get('titulo','Consulta tributária DF')
        plain=soup.get_text(' ',strip=True)
        if len(plain)<200 or not re.search('consulta|parecer',normalize(plain)):raise ValueError('Consulta sem corpo identificável')
    if not relevant(plain):raise ValueError('fora_escopo_iss_icms_simples')
    body=_convert(str(soup),url);sha=digest(raw);sid=kind+'-'+digest(url.encode())[:20];target=Path(output)/sid/sha
    md=('# '+title+'\n\n[Fonte oficial]('+url+') · [Original](original.html)\n\n> Revisão humana pendente. Vigência e aplicabilidade não verificadas. TARF: ementa e decisão disponibilizadas pelo catálogo; não equivale ao inteiro teor do voto.\n\n'+body+'\n').encode()
    if (target/'metadados.json').exists():
        old=json.loads((target/'metadados.json').read_text(encoding='utf-8'))
        if (target/'original.html').read_bytes()!=raw or digest((target/'documento.md').read_bytes())!=old['markdown_sha256'] or old['source_url']!=url:raise ValueError('Cache divergente')
        return old
    target.mkdir(parents=True,exist_ok=True)
    (target/'original.html').write_bytes(raw);(target/'documento.md').write_bytes(md)
    meta=dict(source_id=sid,source_url=url,titulo=title,tipo=kind,status='extraido',original='original.html',originais=[dict(arquivo=str((target/'original.html').resolve()),source_url=url,sha256=sha,bytes=len(raw))],sha256=sha,bytes=len(raw),markdown_arquivo=str((target/'documento.md').resolve()),markdown_sha256=digest(md),coletado_em=datetime.now(timezone.utc).isoformat(),jurisdicao='Distrito Federal',camada='B',revisao_humana='pendente',vigencia='nao_verificada',caracteres=len(plain))
    meta.update(extra or {})
    save_json(target/'metadados.json',meta);return meta

def collect(output=DEFAULT_OUTPUT,start=2010,end=2026,pages=4,page_size=50):
    if not 1990<=start<=end<=2026 or not 1<=pages<=20 or not 1<=page_size<=100:raise ValueError('Limites inválidos')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    records=[];discovery=[];errors=[];skipped=0
    with httpx.Client(timeout=60,follow_redirects=True,verify=_ssl_context(),limits=httpx.Limits(max_connections=3)) as client:
        def request(url,payload=None):
            for attempt in range(3):
                try:
                    r=client.post(url,json=payload) if payload is not None else client.get(url)
                    if r.status_code in (401,403):r.raise_for_status()
                    if r.status_code in (429,500,502,503,504) and attempt<2:time.sleep(1+attempt*2);continue
                    r.raise_for_status()
                    if urlsplit(str(r.url)).hostname not in ('www.receita.fazenda.df.gov.br','ww1.receita.fazenda.df.gov.br'):raise ValueError('Redirect fora da origem')
                    return r.content
                except httpx.TransportError:
                    if attempt==2:raise
                    time.sleep(1+attempt*2)
        def annual(year):
            try:return year,request(API,{'Ano':str(year),'OpcaoPesquisa':'Documento'}),None
            except Exception as e:return year,None,str(e)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for year,raw,error in pool.map(annual,range(start,end+1)):
                if error:errors.append(dict(source_url=API,ano=year,erro=error));continue
                path=output/'catalogos'/str(year)/('resposta-'+digest(raw)+'.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                rows=json.loads(decode(raw));discovery.append(dict(source_url=API,metodo='POST',parametros={'Ano':str(year),'OpcaoPesquisa':'Documento'},arquivo=str(path.resolve()),sha256=digest(raw),bytes=len(raw),resultados=len(rows),paginacao='API retorna array completo; paginação no cliente Angular'))
                for row in rows:
                    html=row.get('DescricaoDocumento') or '';url=CATALOG.replace('informacoes-tributarias-consulta','visualizar-informacoes-tributarias')+'?'+urlencode({k:row[k] for k in ('CodigoTipo','Numero','Ano','CodigoTributo','CodigoAssunto')})
                    try:
                        records.append(ingest(html.encode(),url,output,'consulta_tributaria',dict(titulo=f"{row['NomeTipo']} {row['Numero']}/{row['Ano']}",data_publicacao=row.get('DataPublicacao'),tipo_consulta=row['NomeTipo'],catalog_url=CATALOG,api_url=API,catalogo_arquivo=str(path.resolve()),tributo=row.get('NomeTributo'),assunto=row.get('NomeAssunto'))))
                    except ValueError as e:
                        if str(e).startswith('fora_escopo'):skipped+=1
                        else:errors.append(dict(source_url=url,erro=str(e)))
                print('ano',year,'registros',len(rows),'extraidos',len(records),flush=True)
        urls=set()
        for term in ('ICMS','ISS','Simples Nacional'):
            for page in range(pages):
                params=dict(FromRec=page*page_size+1,NumeroResultados=page_size,PalavrasBusca=term,TipoRecurso=0,CamaraAcordao=0)
                url=TARF+'TelaSaidaListaAcordaos.cfm?'+urlencode(params)
                try:
                    raw=request(url);found=tarf_links(raw);path=output/'catalogos'/'tarf'/('pagina-'+digest(url.encode())[:20]+'-'+digest(raw)+'.html');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                    discovery.append(dict(source_url=url,arquivo=str(path.resolve()),sha256=digest(raw),bytes=len(raw),resultados=len(found),pagina=page+1,termo=term,total_catalogo=(re.search(r' de (\d+) encontrado',BeautifulSoup(decode(raw),'html.parser').get_text(' ',strip=True)).group(1) if re.search(r' de (\d+) encontrado',BeautifulSoup(decode(raw),'html.parser').get_text(' ',strip=True)) else None)));urls.update(found)
                    if len(found)<page_size:break
                except Exception as e:errors.append(dict(source_url=url,erro=str(e)));break
        def decision(url):
            try:return ingest(request(url),url,output,'jurisprudencia_tarf',dict(catalog_url=TARF+'TelaSaidaListaAcordaos.cfm',visao='ementa_e_decisao_catalogo'))
            except Exception as e:return dict(source_url=url,status='erro',erro=str(e))
        with ThreadPoolExecutor(max_workers=3) as pool:
            for record in pool.map(decision,sorted(urls)):
                if record['status']=='erro':
                    if record['erro'].startswith('fora_escopo'):skipped+=1
                    else:errors.append(record)
                else:records.append(record)
    report=dict(total=len(records),extraidos=len(records),falhas=len(errors),fora_escopo=skipped,documentos=records,erros=errors,descoberta=discovery,limites=dict(ano_inicial=start,ano_final=end,paginas_tarf_por_termo=pages,tamanho_pagina=page_size,termos_tarf=['ICMS','ISS','Simples Nacional'],workers_por_host=3),limitacoes=['Consultas: todos os resultados anuais retornados pela API nos anos delimitados, filtrados por corpo com ISS/ICMS/Simples Nacional. Não constitui acervo universal.','TARF: páginas limitadas por termo; busca pode retornar substrings, por isso corpo requer token tributário. Ementa e decisão, não inteiro teor de voto.','Nenhuma autenticação/captcha contornada. Aplicabilidade, tabelas e identidade exigem revisão humana.'])
    manifest=output/'manifesto.json'
    if manifest.exists():
        old=manifest.read_bytes();history=output/'historico'/(digest(old)+'.json');history.parent.mkdir(exist_ok=True);history.write_bytes(old)
    save_json(manifest,report)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);p.add_argument('--start',type=int,default=2010);p.add_argument('--end',type=int,default=2026);p.add_argument('--pages',type=int,default=4);a=p.parse_args();r=collect(a.output,a.start,a.end,a.pages);print(json.dumps({k:r[k] for k in ('total','extraidos','falhas','fora_escopo')}))
