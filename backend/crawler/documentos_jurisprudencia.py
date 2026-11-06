"""Recorte oficial adicional: eventos/rejeições de DF-e e jurisprudência MEI/Simples."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify
from backend.crawler import esquemas, notas_tecnicas_fiscais as nt
from backend.crawler.obrigacoes_avancadas import pdf_text

DEFAULT_OUTPUT=Path(__file__).parent/'data'/'documentos-jurisprudencia'
LIMITES=('Recorte documental limitado, sem busca integral ou paginação de jurisprudência. '
 'Acórdãos são decisões em casos concretos, não normas; consultas CARF preservam ementa/decisão publicada, não comprovam inteiro teor. Informativos e resumos editoriais não são inteiro teor. '
 'Vigência, trânsito em julgado e força vinculante não verificados; revisão humana pendente. '
 'Schemas XSD não são instâncias XML de notas. Não supre lacunas de XMLs nacionais/DF. '
 'Regras de rejeição estão nas notas e anexos originais; não inferimos aplicabilidade universal ao MEI. '
 'Catálogos: uma página por fonte, seleção explícita limitada a 50 arquivos técnicos por catálogo; '
 'não representa todo histórico. PDFs: texto por página, sem reconstrução visual das tabelas.')
ALLOWED={'dfe-portal.svrs.rs.gov.br','www.gov.br','carf.fazenda.gov.br','acordaos.economia.gov.br','scon.stj.jus.br','www.stj.jus.br'}

def official(url):
    p=urlsplit(url)
    return p.scheme=='https' and p.hostname in ALLOWED

def select(catalog,item):
    u=item['url'].lower(); t=item['titulo'].lower()
    if catalog=='nfe':
        return (any(x in u for x in ['moc7-anexo-ii-','moc7-anexo-iii-','moc7-visao-geral',
         'evento_canc_','evento_cce_','evento_epec_','evento_manifestadest_',
         'evento_atorinteressado_','evento_insucessonfe_','evento_econf_',
         'eventos_rtc.zip','schema_evento_211110','pl_009o_nt2024',
         'nt2024.001-crt-mei','nt2019_001_v1_62','nt2023.004_v1.11',
         'nt_2014_001+v1.41','nt_2020.001+v1.50','nt2023.005_v1.02',
         'nt2026.009_v1.00','nt2021.003_v1_50','nt2025.001_v1.01']))
    return any(x in u for x in ['anexo_i-sefin','anexo_ii-sefin','anexo_iii-cnc',
        'anexo_iv-adn','manual-municipios-','manual-contribuintes-apis-adn',
        'manual-contribuintes-emissor-publico-api-emissao-decisao'])

CARF=['11060003191201053_6278557','15504721844201741_6305673',
      '15563720036201923_7334847','13161720988201359_6949211',
      '13555720168201929_6546327','13643720102201516_6653720']
STJ=[('202404354657','20/02/2025'),('202500891299','28/05/2026'),
     ('202500564117','21/08/2025'),('202500432047','01/10/2026')]

def seeds():
    items=[]
    for code in CARF:
        items.append(dict(titulo='CARF Simples Nacional processo '+code.split('_')[0],url='https://acordaos.economia.gov.br/acordaos2/pdfs/processados/'+code+'.pdf',tipo='acordao_administrativo',kind='pdf'))
    for aid in ['8629348','8486687','8202416','8520447','8423757','8390033']:
        items.append(dict(titulo='CARF Simples Nacional acórdão id '+aid,url='https://carf.fazenda.gov.br/sincon/public/pages/ConsultarJurisprudencia/listaJurisprudencia.jsf?idAcordao='+aid,tipo='consulta_acordao_administrativo',kind='html'))
    for reg,date in STJ:
        items.append(dict(titulo='STJ Simples Nacional registro '+reg+' publicação '+date,url='https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?dt_publicacao='+date.replace('/','%2F')+'&num_registro='+reg,tipo='acordao_judicial',kind='pdf'))
    items.append(dict(titulo='CARF MEI atividade não permitida',url='https://carf.fazenda.gov.br/sincon/public/pages/ConsultarJurisprudencia/listaJurisprudencia.jsf?idAcordao=8712620',tipo='consulta_acordao_administrativo',kind='html'))
    items.append(dict(titulo='STJ Informativo872 prescrição no Simples',url='https://scon.stj.jus.br/SCON/GetPDFINFJ?edicao=0872',tipo='informativo_jurisprudencial',kind='pdf'))
    items.append(dict(titulo='STJ panorama jurisprudencial do Simples Nacional (14/09/2025)',url='https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2025/14092025-Simples--mas-nem-tanto-a-jurisprudencia-do-STJ-e-as-regras-aplicaveis-ao-Simples-Nacional.aspx',tipo='resumo_editorial_jurisprudencial',kind='html'))
    return items

def ingest(item,raw,output):
    if not official(item['url']):raise ValueError('Fonte não oficial no recorte.')
    sid=item['source_id']; sha=hashlib.sha256(raw).hexdigest(); path=Path(output)/sid/sha
    if path.exists():
        meta=json.loads((path/'metadados.json').read_text(encoding='utf8'))
        if meta['sha256']!=sha or meta['source_url']!=item['url'] or (path/meta['original']).read_bytes()!=raw or hashlib.sha256((path/meta['markdown_arquivo']).read_bytes()).hexdigest()!=meta['markdown_sha256']:
            raise ValueError('Versão existente incompleta ou divergente.')
        return meta
    kind=item['kind'];extra={}
    if kind=='xsd':
        docs=esquemas.parse_package(raw)
        namespace=next((d['target_namespace'] for d in docs if 'portalfiscal.inf.br/nfe' in d['target_namespace']),None)
        if not namespace:raise ValueError('Namespace NF-e ausente.')
        result=esquemas.ingest(sid,dict(title=item['titulo'],url=item['url'],catalog_url=item['catalog_url'],identity_namespace=namespace),raw,output)
        meta=json.loads((path/'metadados.json').read_text(encoding='utf8')); md=result.read_text(encoding='utf8');ext='zip';extra.update(meta)
    elif kind=='xlsx':
        sheets=nt.parse_xlsx(raw); ext='xlsx';extra['linhas']=sum(len(s['linhas']) for s in sheets)
        md='\n\n'.join('## '+s['nome']+'\n\n'+ '\n'.join(str(r['linha'])+': '+'; '.join(c['celula']+'='+c['valor']+(' [fórmula: '+str(c['formula'])+']' if 'formula' in c else '') for c in r['celulas']) for r in s['linhas'])+'\nMesclagens: '+', '.join(s['mesclagens']) for s in sheets)
        path.mkdir(parents=True);(path/'tabelas.json').write_text(json.dumps(sheets,ensure_ascii=False,indent=2),encoding='utf8')
    elif kind=='pdf':
        pages=pdf_text(raw)
        if not pages or not any(p.strip() for p in pages):raise ValueError('PDF sem texto.')
        if item['tipo'] in ('acordao_administrativo','acordao_judicial','informativo_jurisprudencial'):
            text=' '.join(pages).lower()
            if 'simples' not in text or ('acórdão' not in text and 'acordao' not in text and 'informativo' not in text):raise ValueError('Identidade jurisprudencial ausente.')
        extra['paginas']=len(pages);ext='pdf';md='\n\n'.join('## Página '+str(i)+'\n\n'+p for i,p in enumerate(pages,1))
    else:
        soup=BeautifulSoup(raw.decode('utf8'),'html.parser')
        for node in soup.select('script,style,nav,footer'):node.decompose()
        body=soup.select_one('#content-core') or soup.select_one('body')
        text=body.get_text(' ',strip=True) if body else ''
        identity=['simples nacional','jurisprudência'] if item['tipo']=='resumo_editorial_jurisprudencial' else ['simples nacional','acórdão','ementa']
        if len(text)<200 or not all(t in text.lower() for t in identity):raise ValueError('Consulta jurisprudencial sem conteúdo substantivo.')
        md=markdownify(str(body),heading_style='ATX');ext='html'
    path.mkdir(parents=True,exist_ok=True)
    original='original.'+ext; name='conteudo.md'
    content=('# '+item['titulo']+'\n\nFonte: '+item['url']+'\n\n> '+LIMITES+'\n\n'+md+'\n').encode('utf8')
    meta={**extra,**item,'titulo':item['titulo'],'source_url':item['url'],'original':original,
          'markdown_arquivo':name,'markdown_sha256':hashlib.sha256(content).hexdigest(),
          'sha256':sha,'coletado_em':datetime.now(timezone.utc).isoformat(),
          'camada':'A','status':extra.get('status','extraido'),'vigencia':'nao_verificada','revisao_humana':'pendente',
          'markdown':(path/name).relative_to(output).as_posix(),
          'originais':[{'arquivo':str((path/original).resolve()),'sha256':sha,'source_url':item['url'],'bytes':len(raw)}]}
    (path/original).write_bytes(raw);(path/name).write_bytes(content)
    (path/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    return meta

def save_catalog(output,key,url,raw,links,chosen):
    digest=hashlib.sha256(raw).hexdigest();p=Path(output)/'catalogos'/key/digest
    if p.exists():
        try:
            meta=json.loads((p/'metadados.json').read_text(encoding='utf8'))
            cat=json.loads((p/'catalogo.json').read_text(encoding='utf8'))
            md=p/meta['markdown_arquivo']
            if (meta['source_url']!=url or meta['source_id']!='catalogo-'+key or meta['sha256']!=digest
                    or (p/meta['original']).read_bytes()!=raw
                    or hashlib.sha256(md.read_bytes()).hexdigest()!=meta['markdown_sha256']
                    or cat['source_url']!=url or cat['sha256']!=digest
                    or cat['coletado_em']!=meta['coletado_em'] or cat['selecionados']!=chosen):
                raise ValueError('Catálogo existente divergente.')
        except (OSError,KeyError,ValueError) as exc:
            raise ValueError('Catálogo existente incompleto ou divergente.') from exc
        return cat
    cat=dict(source_url=url,sha256=digest,coletado_em=datetime.now(timezone.utc).isoformat(),total_links=len(links),selecionados=chosen,status='coletado',paginas_consultadas=1,limite_arquivos=50)
    md=('# Catálogo '+key+'\n\nFonte: '+url+'\n\n'+LIMITES+'\n\n'+'\n'.join('- ['+x['titulo']+']('+x['url']+')' for x in chosen)+'\n').encode('utf8')
    metadata={**cat,'source_id':'catalogo-'+key,'titulo':'Catálogo '+key,'tipo':'catalogo_tecnico','camada':'A','original':'original.html','markdown_arquivo':'conteudo.md','markdown_sha256':hashlib.sha256(md).hexdigest(),'vigencia':'nao_verificada','revisao_humana':'pendente'}
    p.mkdir(parents=True)
    (p/'original.html').write_bytes(raw);(p/'conteudo.md').write_bytes(md)
    (p/'metadados.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
    (p/'catalogo.json').write_text(json.dumps(cat,ensure_ascii=False,indent=2),encoding='utf8')
    return cat


def collect(output,client):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);items=[];cats=[];results=[]
    for key,url in [('nfe',nt.SVRS),('nfse',nt.BASE+'documentacao-atual')]:
        try:
            response=client.get(url);response.raise_for_status();raw=response.content
            # Force UTF-8: BeautifulSoup can misidentify official SVRS UTF-8 bytes.
            links=nt.discover(raw.decode('utf8'),url)
            chosen=list({x['url']:x for x in links if select(key,x)}.values())
            if not chosen or len(chosen)>50:raise ValueError('Seleção vazia ou limite50 excedido.')
            cat=save_catalog(output,key,url,raw,links,chosen);cats.append(cat)
            for x in chosen:
                u=x['url'].lower();kind='xsd' if '.zip' in u else 'xlsx' if '.xlsx' in u else 'pdf'
                items.append({**x,'kind':kind,'tipo':'esquemas_xsd' if kind=='xsd' else 'leiaute_regras_eventos' if kind=='xlsx' else 'documentacao_tecnica','catalog_url':url})
        except Exception as exc:cats.append(dict(source_url=url,status='erro',erro=str(exc)))
    items.extend(seeds())
    for item in items:
        item={**item,'source_id':('juris-' if 'carf.' in item['url'] or 'acordaos.' in item['url'] or 'stj.' in item['url'] else 'dfe-')+hashlib.sha256(item['url'].encode()).hexdigest()[:14]}
        try:
            r=client.get(item['url'],timeout=6 if 'acordaos.economia.gov.br' in item['url'] else 25);r.raise_for_status()
            if not official(str(r.url)):raise ValueError('Redirecionamento fora de fonte oficial.')
            result=ingest(item,r.content,output)
        except Exception as exc:result={**item,'source_url':item['url'],'status':'erro','erro':str(exc)}
        results.append(result);print(item['titulo'],result['status'],flush=True)
    report=dict(executado_em=datetime.now(timezone.utc).isoformat(),recorte=LIMITES,catalogos=cats,documentos=results,total=len(results),total_extraidos=sum(r['status']=='extraido' for r in results),total_obtidos=sum(r['status'] in ('extraido','dependencias_pendentes') for r in results),dependencias_pendentes=[{'source_id':r['source_id'],'dependencias':r['dependencias_ausentes']} for r in results if r.get('dependencias_ausentes')],lacunas=['Instâncias XML nacionais/DF não incluídas','Histórico integral e paginação de jurisprudência não incluídos','Vigência e força vinculante não verificadas'])
    (output/'manifesto.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# Documentos fiscais e jurisprudência','',LIMITES,'','| Documento | Tipo | Estado |','|---|---|---|']
    for r in results:lines.append('| ['+r['titulo']+']('+r.get('markdown',r['url'])+') | '+r['tipo']+' | '+r['status']+' |')
    (output/'indice.md').write_text('\n'.join(lines)+'\n',encoding='utf8');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);a=p.parse_args()
    with httpx.Client(timeout=25,follow_redirects=True) as client:r=collect(a.output,client)
    return int(any(x['status']=='erro' for x in r['documentos']+r['catalogos']))
if __name__=='__main__':raise SystemExit(main())
