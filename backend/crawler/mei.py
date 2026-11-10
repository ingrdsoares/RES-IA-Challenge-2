"""Coleta orientações oficiais do Portal do Empreendedor em Markdown."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx
from backend.crawler.paginas import ingest
from backend.crawler.anexos import _write_atomic
BASE='https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/'
SOURCES={
 'por-que-ser-mei':{'title':'Por que ser um MEI?', 'url':BASE+'quero-ser-mei/o-que-e-ser-um-mei','identity':['MEI']},
 'antes-formalizar':{'title':'O que você precisa saber antes de se tornar um MEI','url':BASE+'quero-ser-mei/o-que-voce-precisa-saber-antes-de-se-tornar-um-mei','identity':['antes de se tornar um MEI']},
 'ocupacoes':{'title':'Ocupações permitidas ao MEI','url':BASE+'quero-ser-mei/quais-as-ocupacoes-que-podem-ser-mei','identity':['ocupações','MEI']},
 'perguntas-frequentes':{'title':'Perguntas frequentes MEI','url':BASE+'perguntas-frequentes','identity':['Perguntas Frequentes']},
}
for info in SOURCES.values():info.update(camada='B',kind='orientacao_mei')
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'mei'

def collect(sources, output, client):
 output=Path(output);output.mkdir(parents=True,exist_ok=True);results=[]
 for source in sources:
  info=SOURCES[source]
  try:
   response=client.get(info['url']);response.raise_for_status()
   path=ingest(source,info,response.content,output)
   meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
   results.append({**meta,'markdown':path.relative_to(output).as_posix()})
  except (httpx.HTTPError,ValueError,OSError) as exc:
   recovered=None
   for original in sorted((output/source).glob('*/original.html'),key=lambda p:p.stat().st_mtime,reverse=True):
    try:
     from backend.crawler.paginas import parse_page
     raw=original.read_bytes();parse_page(raw,info)
     path=ingest(source,info,raw,output)
     meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
     if meta['source_url']!=info['url']:continue
     recovered={**meta,'markdown':path.relative_to(output).as_posix(),'observacao':'Snapshot oficial preservado e revalidado; a retentativa de rede falhou. A data de coleta do snapshot permanece nos metadados.','historico':[{'resultado':'falha_na_retentativa','erro':str(exc),'registrado_em':datetime.now(timezone.utc).isoformat()}]}
     break
    except (ValueError,OSError):continue
   results.append(recovered or {'source_id':source,'titulo':info['title'],'source_url':info['url'],'status':'erro','erro':str(exc)})
  print(source+': '+results[-1]['status'],flush=True)
 report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'fontes':results}
 lines=['# Orientações oficiais MEI','','Conjunto inicial do Portal do Empreendedor. Orientações administrativas, camada B. Vigência e aplicabilidade não verificadas. Índice da última execução; versões anteriores permanecem preservadas. O HTML do portal pode conter blocos vazios dependentes de JavaScript: o Markdown representa somente o texto servido e não comprova cobertura integral de cada orientação.','']
 for item in results:
  lines.append('- '+(f"[{item['titulo']}]({item['markdown']})" if 'markdown' in item else item['titulo'])+' — '+item['status'])
  if 'erro' in item:lines.append('  - '+item['erro'])
  if 'observacao' in item:lines.append('  - '+item['observacao'])
 _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2));_write_atomic(output/'indice.md','\n'.join(lines)+'\n')
 return report

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);parser.add_argument('--source',choices=[*SOURCES,'all'],default='all');args=parser.parse_args()
 with httpx.Client(timeout=90,follow_redirects=True) as client:report=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client)
 return int(any(i['status']!='extraido' for i in report['fontes']))
if __name__=='__main__':raise SystemExit(main())
