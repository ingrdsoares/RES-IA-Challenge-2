"""Indicadores empresariais públicos: Observatório Sebrae e boletins Mapa de Empresas.

Recorte: cartões Brasil e 27 UFs publicados no HTML do Observatório (empresas e
empregados), e dois boletins Mapa 2025 selecionados. Não soma ou concilia séries.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime,timezone
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
import pypdfium2

MAPA='https://www.gov.br/empresas-e-negocios/pt-br/mapa-de-empresas'
SOURCES={
 'observatorio-sebrae':{'url':'https://observatorio.sebrae.com.br/','titulo':'Observatório Setorial Territorial Sebrae — cartões Brasil e UFs','kind':'indicadores'},
 'mapa-catalogo':{'url':MAPA,'titulo':'Mapa de Empresas — catálogo','kind':'catalogo'},
 'mapa-2025-q2':{'url':MAPA+'/boletins/mapa-de-empresas-boletim-2o-quadrimestre-2025.pdf/@@display-file/file','titulo':'Mapa de Empresas — 2º quadrimestre 2025','kind':'pdf','periodo':'2025-05/2025-08'},
 'mapa-2025-q1':{'url':MAPA+'/boletins/mapa-de-empresas-boletim-1o-quadrimestre-2025-pdf.pdf/@@download/file','titulo':'Mapa de Empresas — 1º quadrimestre 2025','kind':'pdf','periodo':'2025-01/2025-04'},
 'mapa-df-2025-q1':{'url':'https://jucis.df.gov.br/wp-conteudo/uploads/2020/12/Distrito-Federal-1.pdf','titulo':'JUCIS-DF — Panorama Empresarial, 2ª edição — julho/2025 e 1º quadrimestre 2025','kind':'pdf','periodo':'2025-01/2025-04'},
 'datasebrae':{'url':'https://datasebrae.com.br/totaldeempresas/','titulo':'DataSebrae — Total de Empresas','kind':'acesso'},
}
DEFAULT_OUTPUT=Path(__file__).parent/'data'/'indicadores-empresariais'
UFS=dict(zip(['11','12','13','14','15','16','17','21','22','23','24','25','26','27','28','29','31','32','33','35','41','42','43','50','51','52','53'],['RO','AC','AM','RR','PA','AP','TO','MA','PI','CE','RN','PB','PE','AL','SE','BA','MG','ES','RJ','SP','PR','SC','RS','MS','MT','GO','DF']))

def extract_indicators(raw):
    soup=BeautifulSoup(raw,'html.parser');script=soup.find('script',id='__NEXT_DATA__')
    if not script: raise ValueError('Dados públicos __NEXT_DATA__ ausentes; página sem indicadores')
    data=json.loads(script.string or script.get_text());props=data['props']['pageProps'];stats=props.get('stats');states=props.get('stateStats')
    if not stats or not states or not set(UFS).issubset(states):raise ValueError('Cobertura incompleta: estatísticas Brasil e 27 UFs obrigatórias')
    indicators=[]
    groups=[('BR',stats,'stats')]+[(UFS.get(code,code),values,'stateStats.'+code) for code,values in states.items() if code in UFS]
    for territory,values,pointer in groups:
        for key,label,source,unit in [('companies','Empresas ativas','Receita Federal','empresas'),('employees','Empregados','RAIS','empregados')]:
            item=values.get(key)
            if not isinstance(item,dict) or not item.get('year') or not isinstance(item.get('value'),(str,int,float)) or isinstance(item.get('value'),bool):
                raise ValueError('Indicador sem valor/período: '+territory+'/'+key)
            indicators.append({'territorio':territory,'indicador':label,'valor':item['value'],'periodo':str(item['year']),'unidade':unit,'fonte_original':source,'source_url':SOURCES['observatorio-sebrae']['url'],'json_path':'props.pageProps.'+pointer+'.'+key,'precisao':'arredondado conforme cartão' if isinstance(item['value'],str) else 'inteiro publicado','limite':'Bases e conceitos podem diferir do Mapa de Empresas; não consolidar automaticamente.'})
    return indicators,data

def extract_df_summary(pages,url):
    if len(pages)<38 or 'Cadastro' not in pages[37] or '01/07/2025' not in pages[37]:
        raise ValueError('Identidade/metodologia do Panorama JUCIS-DF não confirmada')
    summary=re.sub(r'\s+',' ',pages[4]);specs=[
        ('Empresas ativas','2025-07-01','empresas',r'possui ([\d.]+) empresas ativas'),
        ('MEIs ativos','2025-07-01','MEIs',r'MEIs, são ([\d.]+) na capital'),
        ('Empresas constituídas (recorte empresas da publicação)','2025-01/2025-04','empresas',r'foram constituídas ([\d.]+) empresas'),
        ('MEIs abertos','2025-01/2025-04','MEIs',r'foram ([\d.]+) aberturas'),
        ('Empresas em serviços, atividade principal','2025-07-01','empresas',r'sendo ([\d.]+) se considerado apenas a atividade principal'),
        ('Empresas em serviços, principal e secundária','2025-07-01','empresas',r'e ([\d.]+) levando em consideração atividade principal e secundária'),
    ];rows=[]
    for label,period,unit,pattern in specs:
        m=re.search(pattern,summary,re.I)
        if not m:raise ValueError('Resumo sem indicador esperado: '+label)
        rows.append({'territorio':'DF','indicador':label,'valor':int(m.group(1).replace('.','')),'periodo':period,'unidade':unit,'fonte_original':'Cadastro Estadual de Empresas da JUCIS-DF / BI, coleta 01/07/2025','source_url':url,'pagina':5,'trecho_original':m.group(0),'precisao':'inteiro publicado','limite':'Recortes empresas e MEIs distintos na publicação; não somar nem comparar automaticamente com RFB/Observatório.'})
    return rows

def extract_mapa_summary(pages,info):
    if len(pages)<5 or '2025' not in pages[0] or 'quadrimestre' not in pages[0].lower():raise ValueError('Identidade do boletim Mapa não confirmada')
    specs=[
        (3,'Empresas ativas no final do quadrimestre','empresas',r'registrou ([\d.]+) empresas ativas'),
        (4,'MEIs ativos no final do quadrimestre','MEIs',r'parcela significativa \(([\d.]+)\)'),
        (4,'Empresas abertas','empresas',r'foram abertas ([\d.]+) empresas'),
        (4,'Empresas fechadas','empresas',r'foram fechadas ([\d.]+) empresas'),
        (4,'MEIs abertos','MEIs',r'Desse montante ([\d.]+) são MEIs'),
        (4,'Saldo de aberturas menos fechamentos','empresas',r'Saldo positivo: ([\d.]+) empresas'),
        (5,'Tempo médio de abertura','horas',r'média de tempo de abertura de empresas no país foi de (\d+) horas'),
    ];rows=[]
    for page,label,unit,pattern in specs:
        text=re.sub(r'\s+',' ',pages[page-1]);m=re.search(pattern,text,re.I)
        if not m:raise ValueError('Boletim sem indicador esperado: '+label)
        rows.append({'territorio':'BR','indicador':label,'valor':int(m.group(1).replace('.','')),'periodo':info['periodo'],'unidade':unit,'fonte_original':'Mapa de Empresas / MEMP / DREI','source_url':info['url'],'pagina':page,'trecho_original':m.group(0),'precisao':'inteiro publicado','limite':'Conceito do Mapa inclui matrizes, filiais e MEIs; estoque exclui Inova Simples. Não conciliar automaticamente com Cadastro JUCIS-DF ou RFB/Sebrae.'})
    return rows

def snapshot(source_id,info,raw,status_code,output):
    digest=hashlib.sha256(raw).hexdigest();dest=Path(output)/source_id/digest[:16];dest.mkdir(parents=True,exist_ok=True)
    kind=info['kind'];pdf=raw.startswith(b'%PDF');fmt='pdf' if pdf else 'json' if raw.lstrip().startswith(b'{') else 'html';original=dest/('original.'+fmt)
    if original.exists() and hashlib.sha256(original.read_bytes()).hexdigest()!=digest:
        raise ValueError('Snapshot existente com original divergente do hash; não sobrescrever')
    if not original.exists():original.write_bytes(raw)
    if not pdf:
        catalog=[{'titulo':a.get_text(' ',strip=True),'url':a['href']} for a in BeautifulSoup(raw,'html.parser').find_all('a',href=True)]
        (dest/'links-publicados.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    now=datetime.now(timezone.utc).isoformat()
    existing=dest/'metadados.json'
    if existing.exists():now=json.loads(existing.read_text(encoding='utf8')).get('coletado_em',now)
    meta={'source_id':source_id,'titulo':info['titulo'],'source_url':info['url'],'sha256':digest,'coletado_em':now,'versao':info.get('periodo','snapshot '+now[:10]),'http_status':status_code,'status':'coletado','revisao_humana':'pendente','original':'original.'+fmt,'publicador':'Sebrae' if 'sebrae' in source_id else 'JUCIS-DF' if '-df-' in source_id else 'Ministério do Empreendedorismo, da Microempresa e da Empresa de Pequeno Porte','camada':'B' if 'sebrae' in source_id else 'A','indicadores':0}
    lines=['# '+info['titulo'],'','Fonte: '+info['url'],'','> Snapshot público. Períodos e conceitos próprios de cada fonte; revisão humana pendente.','']
    try:
        if status_code>=400:raise ValueError(f'HTTP {status_code}; acesso indisponível. Nenhuma tentativa de contornar restrição.')
        if kind=='indicadores':
            rows,data=extract_indicators(raw);meta['indicadores']=len(rows);meta['periodos']=sorted({r['periodo'] for r in rows});meta['territorios']=sorted({r['territorio'] for r in rows})
            for row in rows:row.update(source_id=source_id,source_sha256=digest)
            (dest/'dados-publicos.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');(dest/'indicadores.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
            lines+=['| Território | Indicador | Valor publicado | Unidade | Período | Fonte original |','|---|---|---|---|---|---|']
            for r in rows:lines.append(f"| {r['territorio']} | {r['indicador']} | {r['valor']} | {r['unidade']} | {r['periodo']} | {r['fonte_original']} |")
        elif kind=='pdf':
            if not pdf:raise ValueError('Resposta não é PDF; HTML de indisponibilidade não conta como publicação coletada')
            doc=pypdfium2.PdfDocument(raw);meta['paginas']=len(doc);meta['periodo']=info['periodo'];pages=[]
            for i in range(len(doc)):
                page=doc[i];tp=page.get_textpage();content=tp.get_text_range();pages.append(content);lines+=['## Página '+str(i+1),'',content,''];tp.close();page.close()
            doc.close()
            if source_id in ['mapa-df-2025-q1','mapa-2025-q1','mapa-2025-q2']:
                rows=extract_df_summary(pages,info['url']) if source_id=='mapa-df-2025-q1' else extract_mapa_summary(pages,info)
                meta['indicadores']=len(rows);meta['periodos']=sorted({r['periodo'] for r in rows});meta['territorios']=sorted({r['territorio'] for r in rows})
                for row in rows:row.update(source_id=source_id,source_sha256=digest)
                (dest/'indicadores.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
        else:
            soup=BeautifulSoup(raw,'html.parser');text=soup.get_text(' ',strip=True)
            api=json.loads(raw) if fmt=='json' else None
            if 'servidor de backend' in text:raise ValueError('HTTP 200 com aviso de indisponibilidade do backend; catálogo não validado')
            links=[{'titulo':a.get_text(' ',strip=True),'url':a['href']} for a in soup.find_all('a',href=True) if any(x in a['href'] for x in ['boletim','painel','2025','2026'])]
            if api:
                links=[{'titulo':x.get('title',''),'url':x['@id']} for x in api.get('items',[])];meta['total_catalogo_publicado']=api.get('items_total',len(links));text=json.dumps(api,ensure_ascii=False,indent=2)
            if kind=='catalogo' and not links:raise ValueError('Catálogo sem links esperados')
            meta['links']=len(links);(dest/'catalogo.json').write_text(json.dumps(links,ensure_ascii=False,indent=2),encoding='utf8');lines+=[text]
    except (ValueError,KeyError,TypeError) as exc:
        meta['status']='indisponivel';meta['erro']=str(exc);lines+=['## Limitação','',str(exc)]
    meta['markdown']=(dest/'conteudo.md').relative_to(output).as_posix();(dest/'conteudo.md').write_text('\n'.join(lines)+'\n',encoding='utf8');(dest/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');return meta

def collect(output,client):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);results=[];indicators=[]
    for sid,info in SOURCES.items():
        try:
            try:
                r=client.get(info['url'])
                tls='verificado'
            except httpx.ConnectError as exc:
                if sid!='mapa-df-2025-q1' or 'CERTIFICATE_VERIFY_FAILED' not in str(exc):raise
                # Public document only; isolated session carries no account/cookies.
                with httpx.Client(verify=False,timeout=90,follow_redirects=True) as public:
                    r=public.get(info['url'])
                tls='nao_verificado_certificado_raiz_nao_confiavel'
            meta=snapshot(sid,info,r.content,r.status_code,output)
            if meta['status']!='coletado' and sid.startswith('mapa-') and sid!='mapa-df-2025-q1':
                attempt=meta
                canonical=info['url'].split('/@@')[0]
                if sid=='mapa-catalogo':canonical=MAPA+'/boletins?b_size=100'
                api_url=canonical.replace('/empresas-e-negocios/','/empresas-e-negocios/++api++/',1)
                api_response=client.get(api_url,headers={'Accept':'application/json'});api_response.raise_for_status();api=api_response.json()
                actual=api_url
                if info['kind']=='pdf':
                    actual=api['file']['download'].replace('/empresas-e-negocios/','/empresas-e-negocios/++api++/',1)
                    api_response_download=client.get(actual);api_response_download.raise_for_status()
                    raw=api_response_download.content
                else:raw=api_response.content
                meta=snapshot(sid,{**info,'url':actual},raw,200,output)
                meta.update(url_publicada=info['url'],ultima_tentativa_html=attempt,metadados_api_url=api_url)
                dest=(output/meta['markdown']).parent
                (dest/'metadados-api-original.json').write_bytes(api_response.content)
                meta['metadados_api_sha256']=hashlib.sha256(api_response.content).hexdigest()
            meta['tls']=tls
            if 'markdown' in meta:
                (output/meta['markdown']).with_name('metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
        except (httpx.HTTPError,ValueError,KeyError) as exc:meta={'source_id':sid,'source_url':info['url'],'titulo':info['titulo'],'status':'erro','erro':str(exc),'indicadores':0}
        if meta['status']!='coletado':
            cached=[]
            for path in (output/sid).glob('*/metadados.json'):
                candidate=json.loads(path.read_text(encoding='utf8'))
                if candidate.get('status')=='coletado':cached.append(candidate)
            if cached:
                last=max(cached,key=lambda x:x['coletado_em']);last={**last,'ultima_tentativa':meta,'dados_preservados_de_execucao_anterior':True};meta=last
        results.append(meta);print(sid,meta['status'],meta.get('indicadores',0),flush=True)
        if meta.get('indicadores'):indicators+=json.loads((output/meta['markdown']).with_name('indicadores.json').read_text(encoding='utf8'))
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'recorte':'Dois boletins nacionais Mapa de Empresas 2025 selecionados e relatório distrital JUCIS-DF 1º quadrimestre 2025; cartões públicos Sebrae de empresas e empregados Brasil+27UF. Não é histórico completo. DataSebrae restrito usa alternativa oficial Observatório. HTML sem dados não conta como indicador.','total_fontes':len(results),'fontes_coletadas':sum(x['status']=='coletado' for x in results),'indicadores':len(indicators),'indicadores_df':sum(x['territorio']=='DF' for x in indicators),'fontes':results}
    (output/'indicadores.json').write_text(json.dumps(indicators,ensure_ascii=False,indent=2),encoding='utf8');(output/'manifesto.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# Indicadores empresariais','',report['recorte'],'',f"Indicadores: {len(indicators)}; DF: {report['indicadores_df']}. Fontes indisponíveis permanecem registradas abaixo.",'','| Fonte | Estado | Indicadores | Limitação |','|---|---|---|---|']
    for x in results:lines.append(f"| [{x['titulo']}]({x.get('markdown',x['source_url'])}) | {x['status']} | {x.get('indicadores',0)} | {x.get('erro','')} |")
    (output/'indice.md').write_text('\n'.join(lines)+'\n',encoding='utf8');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);args=p.parse_args()
    with httpx.Client(timeout=90,follow_redirects=True) as c:r=collect(args.output,c)
    return int(any(x['status']!='coletado' for x in r['fontes']))
if __name__=='__main__':raise SystemExit(main())
