"""Recorte versionado de NT RTC e classificações oficiais NF-e/NFS-e/NBS."""
import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin
from xml.etree import ElementTree as ET
import httpx
from bs4 import BeautifulSoup
import pypdfium2

SVRS='https://dfe-portal.svrs.rs.gov.br/Nfe/Documentos'
BASE='https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/'
MDIC='https://www.gov.br/mdic/pt-br/assuntos/sdic/comercio-e-servicos/nbs-nomenclatura-brasileira-de-servicos/arquivos'
CATALOGS={'nfe':SVRS,'nfse-atual':BASE+'documentacao-atual','nfse-rtc':BASE+'rtc','nbs':MDIC}
DEFAULT_OUTPUT=Path(__file__).parent/'data'/'notas-tecnicas-fiscais'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def discover(raw,url):
    soup=BeautifulSoup(raw,'html.parser'); links=[]
    for a in soup.find_all('a',href=True):
        href=a['href']; match=re.search(r"download_arquivo_estatico\('([^']+)',\s*(\d+),\s*'([^']+)'",a.get('onclick',''))
        if match:
            href='https://dfe-portal.svrs.rs.gov.br/'+match.group(1)+'/DownloadArquivoEstatico/?'+urlencode(dict(zip(['sistema','tipoArquivo','nomeArquivo'],match.groups())))
        if href.startswith('#'): continue
        links.append({'titulo':a.get_text(' ',strip=True),'url':urljoin(url,href)})
    return links

def selected(catalog,item):
    u=item['url'].lower();t=item['titulo'].lower()
    if catalog=='nfe': return any(x in t for x in ['2025.002 v1.53','2026.005 v1.00','2026.006 v1.01','2025.002 rt tabela'])
    if catalog=='nfse-atual': return 'anexo_b-' in u or 'anexo-c-indop' in u
    if catalog=='nfse-rtc': return any(x in u for x in ['nt-010-','nota-tecnica-009-','nt-008-','anexovi-leiautesrn_rtc_ibscbs-v1-04-01','anexovii-indop_ibscbs_v1-03-00','anexo_viii-tabela-correlacao-v01-02-00'])
    return 'nbs2-0.csv' in u

def parse_xlsx(raw):
    if not zipfile.is_zipfile(io.BytesIO(raw)): raise ValueError('XLSX inválido')
    sheets=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        for sheet in wb.find('s:sheets',NS):
            rid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'];target=rels[rid]
            path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            root=ET.fromstring(z.read(path));rows=[]
            for row in root.findall('s:sheetData/s:row',NS):
                cells=[]
                for c in row:
                    v=c.find('s:v',NS);value=v.text if v is not None else ''
                    if c.get('t')=='s': value=shared[int(value)]
                    elif c.get('t')=='inlineStr': value=''.join(c.find('s:is',NS).itertext())
                    f=c.find('s:f',NS)
                    cells.append({'celula':c.get('r'),'valor':value or '',**({'formula':f.text} if f is not None else {})})
                if cells: rows.append({'linha':int(row.get('r')),'celulas':cells})
            merged=[m.get('ref') for m in root.findall('s:mergeCells/s:mergeCell',NS)]
            sheets.append({'nome':sheet.get('name'),'linhas':rows,'mesclagens':merged})
    if not sheets or not any(s['linhas'] for s in sheets): raise ValueError('Planilha vazia')
    return sheets

def ingest(item,raw,output):
    digest=hashlib.sha256(raw).hexdigest();sid=item['source_id'];path=Path(output)/sid/digest[:16]
    if path.exists():
        try:
            meta=json.loads((path/'metadados.json').read_text(encoding='utf8'))
            original=path/('original.'+meta['formato'])
            if meta['sha256']!=digest or meta['source_url']!=item['url'] or original.read_bytes()!=raw or not (path/'conteudo.md').is_file():
                raise ValueError('Versão existente incompleta ou divergente')
        except (OSError,KeyError,ValueError) as exc:
            raise ValueError('Versão existente incompleta ou divergente') from exc
        return meta
    path.mkdir(parents=True,exist_ok=True)
    pdf=raw.startswith(b'%PDF');xlsx=raw.startswith(b'PK');fmt='pdf' if pdf else 'xlsx' if xlsx else 'csv'
    if fmt=='csv' and 'nbs2-0.csv' not in item['url']: raise ValueError('Formato inesperado (possível HTML)')
    text=['# '+item['titulo'],'','Fonte: '+item['url'],'','> Vigência não verificada; revisão humana pendente. Valores e coordenadas originais preservados; mesclagens não são preenchidas automaticamente. Fórmulas são preservadas sem recalcular; valores em cache podem estar vazios.','']
    count=0
    if pdf:
        extracted=[]
        doc=pypdfium2.PdfDocument(raw)
        for i in range(len(doc)):
            page=doc[i];tp=page.get_textpage();page_text=tp.get_text_range();extracted.append(page_text);text+=['## Página '+str(i+1),'',page_text,''];tp.close();page.close()
        count=len(doc);doc.close();unit='paginas'
        if not any(value.strip() for value in extracted): raise ValueError('PDF sem texto suficiente')
    elif xlsx:
        sheets=parse_xlsx(raw);(path/'tabelas.json').write_text(json.dumps(sheets,ensure_ascii=False,indent=2),encoding='utf8');unit='linhas';count=sum(len(s['linhas']) for s in sheets)
        for s in sheets:
            text+=['## '+s['nome'],'','| Linha | Células originais |','|---|---|']
            for row in s['linhas']:
                val='; '.join(c['celula']+'='+(c['valor']+(' [fórmula: '+str(c['formula'])+']' if 'formula' in c else '')).replace('|','\\|').replace('\n','<br>') for c in row['celulas']);text.append(f"| {row['linha']} | {val} |")
            text+=['','Mesclagens: '+', '.join(s['mesclagens']),'']
    else:
        try: decoded=raw.decode('utf-8-sig')
        except UnicodeDecodeError: decoded=raw.decode('cp1252')
        rows=list(csv.reader(io.StringIO(decoded),delimiter=';'))
        if not rows or 'NBS' not in rows[0][0].upper(): raise ValueError('Identidade NBS ausente')
        count=len(rows)-1;unit='linhas';(path/'tabelas.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');text+=['```csv',decoded,'```']
    original=path/('original.'+fmt);original.write_bytes(raw)
    meta={**item,'source_url':item['url'],'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),'versao':item['titulo'],'status':'coletado','camada':'A','tipo':'documentacao_tecnica','revisao_humana':'pendente','vigencia':'nao_verificada',unit:count,'formato':fmt,'markdown':(path/'conteudo.md').relative_to(output).as_posix()}
    (path/'conteudo.md').write_text('\n'.join(text),encoding='utf8');(path/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');return meta

def collect(output,client):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);items=[];catalogs=[]
    for name,url in CATALOGS.items():
        try:
            r=client.get(url);r.raise_for_status();raw=r.content;links=discover(raw,url);chosen=[x for x in links if selected(name,x)]
            # Several official links may point to the same file.
            chosen=list({x['url'].removesuffix('/view'):x for x in chosen}.values())
            sha=hashlib.sha256(raw).hexdigest();p=output/'catalogos'/name/sha[:16];p.mkdir(parents=True,exist_ok=True);(p/'original.html').write_bytes(raw)
            cat={'source_id':name,'source_url':url,'sha256':sha,'coletado_em':datetime.now(timezone.utc).isoformat(),'links':links,'selecionados':chosen,'total_links':len(links),'total_selecionados':len(chosen),'status':'coletado'}
            (p/'catalogo.json').write_text(json.dumps(cat,ensure_ascii=False,indent=2),encoding='utf8');(p/'metadados.json').write_text(json.dumps({**cat,'camada':'A','tipo':'catalogo_tecnico','vigencia':'nao_verificada','revisao_humana':'pendente'},ensure_ascii=False,indent=2),encoding='utf8');catalogs.append({k:v for k,v in cat.items() if k!='links'})
            if not chosen: raise ValueError('Catálogo sem itens no recorte esperado')
            for i,item in enumerate(chosen,1):
                item={**item,'url':item['url'].removesuffix('/view'),'source_id':f'{name}-{i:02}','catalog_url':url}
                try:
                    r=client.get(item['url']);r.raise_for_status();result=ingest(item,r.content,output)
                except Exception as exc: result={**item,'source_url':item['url'],'status':'erro','erro':str(exc)}
                print(item['source_id'],result['status'],flush=True);items.append(result)
        except Exception as exc: catalogs.append({'source_url':url,'status':'erro','erro':str(exc)})
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'recorte':'NT RTC NF-e selecionadas e NFS-e NT008/009/010, anexos atuais de classificação/correlação e NBS2.0; não cobre todas as NT históricas. Versão informada é o rótulo publicado, sem presumir vigência.','catalogos':catalogs,'documentos':items,'total':len(items)}
    (output/'manifesto.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# Notas técnicas e classificações fiscais','',report['recorte'],'','| Documento | Estado | Quantidade |','|---|---|---|']
    for x in items: lines.append(f"| [{x['titulo']}]({x.get('markdown',x['url'])}) | {x['status']} | {x.get('paginas',x.get('linhas',''))} |")
    (output/'indice.md').write_text('\n'.join(lines)+'\n',encoding='utf8');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);a=p.parse_args()
    with httpx.Client(timeout=120,follow_redirects=True) as client: report=collect(a.output,client)
    return int(any(x['status']=='erro' for x in report['documentos']+report['catalogos']))
if __name__=='__main__':raise SystemExit(main())
