"""Preserva CTG 1000 e recorta os artigos 1.179 a 1.195 do Código Civil oficial."""
import argparse
from datetime import datetime,timezone
import hashlib,json,re,shutil,tempfile
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from backend.crawler.anexos import _write_atomic
from backend.crawler.legislacao import _convert
from backend.crawler.manuais import ingest as ingest_pdf
CTG={'title':'CTG 1000 — Adoção plena da NBC TG 1000','url':'https://www1.cfc.org.br/sisweb/SRE/docs/CTG1000.pdf','identity':['ctg 1000','adocao plena'],'camada':'C','kind':'norma_contabil','publicador':'Conselho Federal de Contabilidade','catalog_url':'https://cfc.org.br/tecnica/normas-brasileiras-de-contabilidade/normas-simplificadas-para-pmes/'}
CC_URL='https://www2.camara.leg.br/legin/fed/lei/2002/lei-10406-10-janeiro-2002-432893-normaatualizada-pl.html'
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'complemento-contabil'

def extract_articles(raw):
 soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser')
 if '10.406' not in soup.get_text(' ',strip=True):raise ValueError('Fonte sem identidade da Lei 10.406.')
 found=[];selected=[];active=False
 for node in soup.find_all('p'):
  match=re.match(r'^Art\.\s*([\d.]+)',node.get_text(' ',strip=True))
  if match:
   number=int(match[1].replace('.',''));active=1179<=number<=1195
   if active:found.append(number);selected.append(f'<h2>Art. {number:,}</h2>'.replace(',','.'))
  if active:selected.append(str(node))
 if set(found)!=set(range(1179,1196)):raise ValueError('Recorte incompleto dos artigos 1.179 a 1.195.')
 return found,_convert(''.join(selected),CC_URL)

def ingest_civil(raw,output):
 articles,body=extract_articles(raw);digest=hashlib.sha256(raw).hexdigest();target=Path(output)/'codigo-civil'/digest
 meta={'source_id':'codigo-civil','titulo':'Código Civil — artigos 1.179 a 1.195','source_url':CC_URL,'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),'camada':'A','status':'extraido','artigos':articles,'total_artigos':len(set(articles)),'vigencia':'nao_verificada','revisao':'pendente','recorte':'artigos 1.179 a 1.195; original.html preserva a página completa'}
 if target.exists():
  if (target/'original.html').read_bytes()!=raw or not all((target/n).exists() for n in ['recorte.md','metadados.json']):raise ValueError('Versão existente incompleta ou divergente.')
  return target/'recorte.md'
 target.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.coleta-',dir=target.parent))
 try:
  (stage/'original.html').write_bytes(raw)
  (stage/'recorte.md').write_text('# Código Civil — artigos 1.179 a 1.195\n\nFonte: '+CC_URL+'\n\n> Recorte de escrituração. O original integral da página está preservado em original.html. Vigência e aplicabilidade não verificadas.\n\n'+body,encoding='utf-8')
  (stage/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');stage.rename(target)
 finally:
  if stage.exists():shutil.rmtree(stage)
 return target/'recorte.md'

def collect(output,client):
 output=Path(output);output.mkdir(parents=True,exist_ok=True);results=[]
 for source,info in [('ctg1000',CTG),('codigo-civil',{'title':'Código Civil — artigos 1.179 a 1.195','url':CC_URL})]:
  try:
   response=client.get(info['url']);response.raise_for_status()
   path=ingest_pdf(source,response.content,output,source_info=info) if source=='ctg1000' else ingest_civil(response.content,output)
   meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'));results.append({**meta,'markdown':path.relative_to(output).as_posix()})
  except (httpx.HTTPError,ValueError,OSError) as exc:results.append({'source_id':source,'titulo':info['title'],'source_url':info['url'],'status':'erro','erro':str(exc)})
  print(source+': '+results[-1]['status'],flush=True)
 report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'fontes':results}
 lines=['# Complemento contábil','','CTG 1000 (camada C) e recorte do Código Civil (camada A). Publicação, vigência, alterações e aplicabilidade exigem revisão.','']
 for item in results:
  lines.append('- '+(f"[{item['titulo']}]({item['markdown']})" if 'markdown' in item else item['titulo'])+' — '+item['status'])
  if 'erro' in item:lines.append('  - '+item['erro'])
 _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2));_write_atomic(output/'indice.md','\n'.join(lines)+'\n');return report

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);args=parser.parse_args()
 with httpx.Client(timeout=90,follow_redirects=True) as client:report=collect(args.output,client)
 return int(any(i['status']!='extraido' for i in report['fontes']))
if __name__=='__main__':raise SystemExit(main())
