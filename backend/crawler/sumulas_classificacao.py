"""Bounded official CARF and merchandise-classification documentary collection."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import io
import re
import unicodedata
import zipfile
from defusedxml import ElementTree as SafeET
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify
from .consultas_rfb import cached, digest, extract_pdf, save_json, stamp
from .catalogo import audit_snapshot, Hasher

CARF='https://www.gov.br/carf/pt-br/jurisprudencia/sumulas-carf/'
RFB='https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/classificacao-fiscal-de-mercadorias'
SEEDS=[CARF+s for s in ['sumulas-carf','sumulas-consolidadas-com-os-acordaos-precedentes','sumulas-consolidadas-arquivos','sumulas-por-materia','sumulas-por-materia-arquivos']]+[RFB]
NCM='https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json'
SEEDS.append(NCM)
OUTPUT=Path(__file__).parent/'data'/'sumulas-classificacao'

def links(raw,url):
    soup=BeautifulSoup(raw,'html.parser');body=soup.select_one('#content-core') or soup.select_one('#parent-fieldname-text') or soup.select_one('.texto-dou') or soup.select_one('main')
    if body is None: raise ValueError('Missing official editorial content')
    found={}
    for a in body.find_all('a',href=True):
        u=urldefrag(urljoin(url,a['href']))[0].removesuffix('/view').removesuffix('/@@download/file')
        if urlsplit(u).scheme!='https': continue
        if u.startswith(CARF) or u.startswith(RFB): found[u]=a.get_text(' ',strip=True) or u.rsplit('/',1)[-1]
        elif url.startswith((CARF,RFB)) and urlsplit(u).hostname=='www.in.gov.br' and '/web/dou/-/' in u: found[u]=a.get_text(' ',strip=True) or u.rsplit('/',1)[-1]
        elif '.pdf' in urlsplit(u).path.lower() and urlsplit(u).hostname in ('www.gov.br','carf.economia.gov.br','carf.fazenda.gov.br'): found[u]=a.get_text(' ',strip=True)
    return found

def extract_docx(raw):
    """Plain OOXML paragraphs and table rows; no executable content or extraction."""
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if '[Content_Types].xml' not in z.namelist(): raise ValueError('Not an OOXML document')
        info=z.getinfo('word/document.xml')
        if info.file_size>20_000_000: raise ValueError('DOCX XML exceeds bounded size')
        root=SafeET.fromstring(z.read(info));body=root.find('w:body',ns)
        if body is None: raise ValueError('DOCX body absent')
        lines=['> Extração OOXML simples: parágrafos e células em ordem. Formatação, imagens, campos, cabeçalhos/rodapés, comentários e revisões não são reproduzidos. Modelo de petição não é norma.','']
        for node in body:
            if node.tag.endswith('}p'):
                lines+=[''.join(node.itertext()) if not node.findall('.//w:t',ns) else ''.join(t.text or '' for t in node.findall('.//w:t',ns)), '']
            elif node.tag.endswith('}tbl'):
                for row in node.findall('w:tr',ns):
                    lines.append(' | '.join(''.join(t.text or '' for t in cell.findall('.//w:t',ns)).replace('|','\\|') for cell in row.findall('w:tc',ns)))
                lines.append('')
        if not root.findall('.//w:t',ns): raise ValueError('DOCX has no text')
    return '\n'.join(lines)

def precedent_inventory(output,items):
    """Count explicit source headings, not general mentions of a súmula."""
    u=CARF+'sumulas-consolidadas-com-os-acordaos-precedentes'
    item=next(m for m in items if m['source_url']==u)
    raw=Path(item['originais'][0]['arquivo']).read_bytes()
    soup=BeautifulSoup(raw,'html.parser');body=soup.select_one('#content-core')
    def norm(text): return ''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))
    headings=[]
    for tag in body.find_all(['strong','b','h2','h3','h4']):
        value=norm(tag.get_text(' ',strip=True))
        match=re.fullmatch(r'Sumula CARF n[ºo°.]?\s*(\d+)',value,re.I)
        if match: headings.append(int(match.group(1)))
    alltext=norm(body.get_text(' ',strip=True))
    refs=re.findall(r'Acordao\s+n[ºo°.]?\s*([0-9]{3,4}[-.][0-9.]{4,8})',alltext,re.I)
    numbers=sorted(set(headings));unique=sorted(set(refs))
    result=dict(source_url=u,source_sha256=item['sha256'],metodo='Números de títulos strong/b/h2-h4 com correspondência integral; acórdãos são referências textuais explícitas, não íntegras.',sumulas_titulos=len(headings),sumulas_numeros_distintos=len(numbers),sumulas_numeros=numbers,acordaos_referencias=len(refs),acordaos_identificadores_distintos=len(unique),acordaos_identificadores=unique,acordaos_integras_confirmadas=0,limites='Quadro inclui súmulas históricas/revogadas; contagem não afirma vigência. Identificadores repetidos deduplicados literalmente. Não há links para as íntegras dos precedentes neste quadro. NESH contém notas explicativas; notas legais standalone Classif não coletadas.')
    save_json(output/'inventario-sumulas-precedentes.json',result)
    return {k:v for k,v in result.items() if k not in ('sumulas_numeros','acordaos_identificadores')}

def enrich_metadata(meta,folder):
    """Enrich review/authority facts without rewriting originals or first dates."""
    meta=dict(meta);u=meta['source_url'];original=meta['original']
    nature=('modelo_peticao_sem_forca_normativa' if original.endswith('.docx') else 'ato_normativo_administrativo' if 'portaria' in u.lower() or urlsplit(u).hostname=='www.in.gov.br' else 'quadro_sumulas_com_referencias_precedentes' if '/carf/' in u else 'tabela_ncm_oficial' if u==NCM else 'documentacao_classificacao_oficial')
    meta['natureza_documental']=nature;meta['tipo']=nature
    meta['camada']='A' if nature in ('ato_normativo_administrativo','tabela_ncm_oficial') else 'B'
    if u==NCM:
        rows=json.loads((folder/original).read_bytes())['Nomenclaturas']
        leaves=sum(bool(re.fullmatch(r'\d{4}\.\d{2}\.\d{2}',str(row.get('Codigo','')))) for row in rows)
        meta['ncm_registros_hierarquicos']=len(rows)
        meta['ncm_codigos_oito_digitos']=leaves
        meta['ncm_niveis_intermediarios']=len(rows)-leaves
        meta['limite_classificacao']='Registros incluem capítulos, posições, subposições e códigos de oito dígitos; total de registros não é total de códigos finais. Validade temporal e aplicação exigem revisão.'
    if original.endswith('.pdf'):
        text=(folder/meta['markdown_arquivo']).read_text(encoding='utf8')
        chunks=re.split(r'^## Página (\d+)\s*$',text,flags=re.M)
        blanks=[int(chunks[i]) for i in range(1,len(chunks),2) if not chunks[i+1].strip()]
        meta['paginas_sem_texto']=blanks
        meta['paginas_sem_texto_total']=len(blanks)
        verified=set()
        for evidence in meta.get('paginas_em_branco_verificadas',[]):
            image=Path(evidence['imagem_arquivo'])
            if evidence.get('pdf_sha256')==meta.get('sha256') and image.is_file() and digest(image.read_bytes())==evidence.get('imagem_sha256'):
                verified.add(evidence['pagina'])
        pending=[page for page in blanks if page not in verified]
        meta['paginas_ocr_pendentes']=pending
        if blanks:
            meta['status']='parcial' if pending else 'extraido'
            meta['ocr_revisao_pendente']=bool(pending)
            meta['limite_extracao']=('Página sem texto pode ser imagem, separador ou página realmente vazia; OCR/revisão pendente nas páginas listadas em paginas_ocr_pendentes.' if pending else 'Todas as páginas sem texto extraído foram renderizadas e verificadas visualmente em branco; evidências PNG vinculadas ao hash do PDF. Revisão jurídica permanece pendente.')
    return meta

def ingest(url,raw,output,title=''):
    sha=digest(raw);sid=digest(url.encode())[:16];folder=output/'snapshots'/sid/(sha+'-ncm-v2' if url==NCM else sha)
    mp=folder/'metadados.json'
    if mp.exists():
        meta=json.loads(mp.read_bytes())
        if digest((folder/meta['original']).read_bytes())!=sha or digest((folder/meta['markdown_arquivo']).read_bytes())!=meta['markdown_sha256']: raise ValueError('Snapshot modified')
        enriched=enrich_metadata(meta,folder)
        if enriched!=meta: save_json(mp,enriched)
        return enriched
    pdf=raw.startswith(b'%PDF-');isjson=url==NCM;docx=raw.startswith(b'PK') and urlsplit(url).path.lower().endswith('.docx');ext='pdf' if pdf else 'json' if isjson else 'docx' if docx else 'html'
    if isjson:
        data=json.loads(raw);rows=data.get('Nomenclaturas',[])
        if not rows: raise ValueError('NCM sem nomenclaturas')
        title='NCM — tabela oficial completa';n=0
        body='Data da fonte: '+str(data.get('Data_Ultima_Atualizacao_NCM',data.get('Data_Ultima_Atualizacao')))+'\nAto: '+str(data.get('Ato',''))+'\n\n'+ '\n'.join('```json\n'+json.dumps(row,ensure_ascii=False)+'\n```' for row in rows)
    elif docx:
        body=extract_docx(raw);n=0
    elif pdf:
        pages=extract_pdf(raw)
        if not any(p.strip() for p in pages): raise ValueError('PDF requires OCR')
        body='\n\n'.join('## Página '+str(i+1)+'\n\n'+p for i,p in enumerate(pages));n=len(pages)
    else:
        soup=BeautifulSoup(raw,'html.parser');content=soup.select_one('#content-core') or soup.select_one('#parent-fieldname-text') or soup.select_one('.texto-dou') or soup.select_one('main')
        if content is None or not content.get_text(strip=True): raise ValueError('Missing editorial content or blocked response')
        h=soup.find('h1');title=h.get_text(' ',strip=True) if h else title
        for a in content.find_all('a',href=True): a['href']=urljoin(url,a['href'])
        body=markdownify(str(content),heading_style='ATX');n=0
    folder.mkdir(parents=True,exist_ok=True);original='original.'+ext
    (folder/original).write_bytes(raw)
    text=('# '+title+'\n\nFonte: '+url+'\n\n> Súmulas, precedentes, atos normativos e classificações possuem autoridades e âmbitos distintos. Vigência e aplicação ao produto/contribuinte exigem revisão. Acórdãos citados sem íntegra local são dependências pendentes.\n\n'+body).encode()
    (folder/'documento.md').write_bytes(text)
    receipt=output/'requests'/(digest(url.encode())+'.bin.receipt.json')
    date=json.loads(receipt.read_bytes())['coletado_em'] if receipt.exists() else stamp()
    meta=dict(source_id=sid,source_url=url,titulo=title,sha256=sha,original=original,originais=[dict(arquivo=str((folder/original).resolve()),source_url=url,sha256=sha,bytes=len(raw))],markdown_arquivo='documento.md',markdown_sha256=digest(text),coletado_em=date,camada='B',tipo='sumula_precedentes_e_atos' if '/carf/' in url else 'classificacao_fiscal_oficial',vigencia='nao_verificada',revisao_humana='pendente',status='extraido',paginas_pdf=n)
    meta=enrich_metadata(meta,folder)
    save_json(mp,meta);return meta

def run(output=OUTPUT,workers=3,max_documents=1000,max_depth=3):
    if not 1<=workers<=4: raise ValueError('workers must be 1..4')
    output=Path(output);todo={u:u.rsplit('/',1)[-1] for u in SEEDS};seen=set();items=[];failures=[];edges=[]
    with httpx.Client(follow_redirects=True,timeout=60,headers={'User-Agent':'FiscalResearchCollector/1.0 (public documents; bounded)'}) as client:
        for depth in range(max_depth+1):
            batch=sorted((u,t) for u,t in todo.items() if u not in seen)[:max_documents-len(seen)];todo={}
            if not batch: break
            def fetch(pair):
                u,t=pair
                try:
                    raw=cached(client,output/'requests'/(digest(u.encode())+'.bin'),'GET',u,delay=.3)
                    meta=ingest(u,raw,output,t)
                    return u,meta,({} if raw.startswith((b'%PDF-',b'PK')) or u==NCM else links(raw,u)),None
                except Exception as e:return u,None,{},str(e)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for u,meta,discovered,error in pool.map(fetch,batch):
                    seen.add(u)
                    if error:failures.append(dict(url=u,erro=error));continue
                    items.append(meta)
                    for v,title in discovered.items():
                        edges.append(dict(origem=u,destino=v,titulo=title))
                        if v not in seen:todo[v]=title
            save_json(output/'checkpoint.json',dict(visitados=len(seen),snapshots=len(items),falhas=failures,profundidade=depth))
    missing=sorted({e['destino'] for e in edges}-seen)
    hasher=Hasher();audits=[]
    for p in (output/'snapshots').glob('*/*/metadados.json'):
        m=json.loads(p.read_bytes());a=audit_snapshot(m,p,output.resolve(),hasher);audits.append(a)
    save_json(output/'auditoria.json',audits)
    report=dict(coletado_em=stamp(),status='parcial',limites=dict(max_documents=max_documents,max_depth=max_depth,workers=workers),seeds=SEEDS,snapshots=len(items),snapshots_armazenados=len(audits),originais_distintos=len({m['sha256'] for m in items}),paginas_pdf=sum(m['paginas_pdf'] for m in {m['sha256']:m for m in items}.values()),paginas_pdf_snapshots=sum(m['paginas_pdf'] for m in items),visitados=len(seen),links_descobertos=len({e['destino'] for e in edges}),pendentes=missing,falhas=failures,escopo='Recorte finito por links editoriais oficiais; total universal não declarado pela fonte. Não equivale à totalidade das súmulas, acórdãos ou decisões NCM. Classif dinâmico não percorrido; atos DOU ligados diretamente às páginas CARF/RFB tentados em um salto, sem contornar bloqueios. Referências a acórdãos sem íntegra são dependências pendentes.',documentos=items,arestas=edges)
    report['inventario_sumulas_precedentes']=precedent_inventory(output,items)
    save_json(output/'manifest.json',report)
    (output/'manifesto.json').write_bytes((output/'manifest.json').read_bytes())
    (output/'index.md').write_text('# Súmulas CARF e classificação fiscal\n\n'+report['escopo']+'\n\n'+f"Snapshots: {len(items)}; originais distintos: {report['originais_distintos']}; páginas PDF: {report['paginas_pdf']}; falhas: {len(failures)}; links pendentes por limite: {len(missing)}.\n\n"+'\n'.join(f"- [{m['titulo']}]({m['source_url']}) — {m['sha256']}" for m in items),encoding='utf8')
    (output/'indice.md').write_bytes((output/'index.md').read_bytes())
    return {k:v for k,v in report.items() if k not in ('documentos','arestas','pendentes','falhas')},failures

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=OUTPUT);p.add_argument('--workers',type=int,default=3);p.add_argument('--max-documents',type=int,default=1000);p.add_argument('--max-depth',type=int,default=3);a=p.parse_args();print(json.dumps(run(a.output,a.workers,a.max_documents,a.max_depth),ensure_ascii=False,indent=2))
