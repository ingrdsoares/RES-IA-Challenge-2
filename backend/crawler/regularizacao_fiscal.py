"""Orientações públicas RFB/PGFN para regularização, sem consultar contribuintes."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import httpx
from .anexos import _cell,_write_atomic
from .paginas import ingest as ingest_page
from .manuais import ingest as ingest_pdf

GOV='https://www.gov.br/'
PGFN=GOV+'pgfn/pt-br/servicos/'
SOURCES={
 'rfb-parcelamento-sn':{'title':'Parcelar dívidas do Simples Nacional','url':GOV+'pt-br/servicos/parcelar-imposto-simples','identity':['Simples Nacional'],'format':'html'},
 'rfb-parcelamento-mei':{'title':'Parcelar dívidas do MEI','url':GOV+'pt-br/servicos/parcelar-imposto-mei','identity':['MEI'],'format':'html'},
 'certidao-fazenda-nacional':{'title':'Emitir certidão de regularidade fiscal perante a Fazenda Nacional','url':GOV+'pt-br/servicos/emitir-certidao-de-regularidade-fiscal-perante-a-fazenda-nacional','identity':['certidao','fiscal'],'format':'html'},
 'consultar-certidoes':{'title':'Consultar certidões emitidas RFB/PGFN','url':GOV+'pt-br/servicos/consultar-certidoes-emitidas-pela-receita-federal-e-ou-procuradoria-geral-da-fazenda-nacional','identity':['certidoes'],'format':'html'},
 'liberar-certidao-pgfn':{'title':'Liberar emissão de certidão perante a PGFN','url':GOV+'pt-br/servicos/liberar-emissao-de-certidao-de-regularidade-fiscal-perante-a-pgfn','identity':['certidao','PGFN'],'format':'html'},
 'pgfn-primeiros-passos':{'title':'PGFN — primeiros passos na dívida ativa','url':PGFN+'orientacoes-contribuintes/primeiros-passos-1/primeiros-passos','identity':['REGULARIZE','divida'],'format':'html','content_selector':'#content'},
 'pgfn-servicos-divida-ativa':{'title':'PGFN — Carta de Serviços da Dívida Ativa','url':PGFN+'orientacoes-contribuintes/orientacoes-da-divida-ativa','identity':['Divida Ativa'],'format':'html'},
 'pgfn-parcelamentos':{'title':'PGFN — orientações de parcelamento','url':PGFN+'orientacoes-contribuintes/parcelamentos-1/parcelamentos-1','identity':['parcelamento'],'format':'html'},
 'pgfn-faq-sn':{'title':'PGFN — regularização para manutenção no Simples Nacional','url':PGFN+'perguntas-frequentes/simples-nacional-regularizacao-das-pendencias-para-a-manutencao-no-simples-nacional','identity':['Simples Nacional','regularizacao'],'format':'html'},
 'manual-parcelamento-mei':{'title':'Manual do Parcelamento do MEI — RFB','url':'https://www8.receita.fazenda.gov.br/SimplesNacional/Arquivos/manual/Manual_Parcelamento_MEI.pdf','identity':['parcelamento','mei'],'format':'pdf','kind':'manual_regularizacao','publicador':'Receita Federal / Simples Nacional'},
}
SOURCES.update({
 'rfb-situacao-fiscal':{'title':'Consultar dívidas e pendências fiscais — orientações','url':GOV+'pt-br/servicos/consultar-dividas-e-pendencias-fiscais','identity':['pendencias','fiscais'],'format':'html'},
 'rfb-faq-parcelamento':{'title':'RFB — perguntas e respostas de parcelamento Simples','url':GOV+'receitafederal/pt-br/assuntos/orientacao-tributaria/pagamentos-e-parcelamentos/parcelamento-simples-nacional/perguntas-e-respostas','identity':['parcelamento','Simples Nacional'],'format':'html'},
 'pgfn-faq-parcelamentos':{'title':'PGFN — perguntas frequentes de parcelamentos','url':PGFN+'perguntas-frequentes/parcelamentos','identity':['parcelamento','Simples Nacional'],'format':'html'},
})
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'regularizacao-fiscal'

def collect(sources,output,client):
 output=Path(output);output.mkdir(parents=True,exist_ok=True);results=[]
 for source in sources:
  info=SOURCES[source]
  try:
   response=client.get(info['url']);response.raise_for_status()
   path=(ingest_pdf(source,response.content,output,source_info=info) if info['format']=='pdf' else ingest_page(source,info,response.content,output))
   meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
   results.append({**meta,'markdown':path.relative_to(output).as_posix()})
  except (httpx.HTTPError,ValueError,OSError) as exc:
   results.append({'source_id':source,'titulo':info['title'],'source_url':info['url'],'status':'erro','erro':str(exc)})
  print(source,results[-1]['status'],flush=True)
 report={'executado_em':datetime.now(timezone.utc).isoformat(),'escopo':'orientacoes_publicas_sem_consulta_individual','total':len(results),'status':'coleta_concluida' if all(r['status']=='extraido' for r in results) else 'parcial','documentos':results,'limites':'Recorte de orientações e manual publicados pela Receita/PGFN. Nenhuma consulta individual, certidão pessoal, adesão ou negociação foi realizada. Condições, prazos e aplicabilidade exigem revisão da edição e competência; links a sistemas autenticados são referências.'}
 lines=['# Regularização fiscal — RFB e PGFN','',report['limites'],'','| Fonte | Estado | Páginas |','|---|---|---|']
 for r in results:
  title=_cell(r['titulo']);link=f'[{title}]({r["markdown"]})' if 'markdown' in r else title
  lines.append(f'| {link} | {r["status"]} | {r.get("paginas", "")} |')
  if r.get('erro'):lines.extend(['',f'> {r["source_id"]}: {_cell(r["erro"])}',''])
 _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2));_write_atomic(output/'indice.md','\n'.join(lines)+'\n')
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);p.add_argument('--source',choices=[*SOURCES,'all'],default='all');a=p.parse_args()
 with httpx.Client(timeout=90,follow_redirects=True) as client:r=collect(list(SOURCES) if a.source=='all' else [a.source],a.output,client)
 print(f'Fontes: {r["total"]}; estado: {r["status"]}; índice: {a.output/"indice.md"}')
 return int(r['status']!='coleta_concluida')
if __name__=='__main__':raise SystemExit(main())
