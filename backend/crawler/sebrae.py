"""Estudos públicos Sebrae: originais PDF e extração Markdown auditável."""
import argparse
from pathlib import Path
import httpx
from . import manuais

DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'sebrae'
SOURCES={
 'sobrevivencia-2020':{'title':'Sobrevivência de Empresas — apresentação executiva (abril de 2021)','url':'https://datasebrae.com.br/wp-content/uploads/2021/06/Apresenta%C3%A7%C3%A3o-Sobreviv%C3%AAncia_2020_Web_Final.pdf','identity':['sobrevivencia','abril 2021'],'kind':'estudo','catalog_url':'https://datasebrae.com.br/','camada':'B','publicador':'Sebrae / DataSebrae'},
 'pulso-2023-3-uf':{'title':'Pulso dos Pequenos Negócios — 3ª edição, resultados por UF (24/04 a 02/05/2023)','url':'https://datasebrae.com.br/wp-content/uploads/2023/06/Pulso-dos-peq-neg-3a-edicao-UF.pdf','identity':['pulso dos pequenos negocios','2023'],'kind':'estudo','catalog_url':'https://go.agenciasebrae.com.br/economia-e-politica/aumento-dos-custos-afeta-80-das-pequenas-empresas/','camada':'B','publicador':'Sebrae / DataSebrae'},
}

def collect(sources,output,client):
    import json
    from datetime import datetime,timezone
    from .anexos import _write_atomic
    output=Path(output);output.mkdir(parents=True,exist_ok=True);results=[]
    for source in sources:
        info=SOURCES[source]
        try:
            response=client.get(info['url']);response.raise_for_status()
            path=manuais.ingest(source,response.content,output,source_info=info)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc:results.append({'source_id':source,'status':'erro','erro':str(exc)})
        print(source,results[-1]['status'],flush=True)
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'limitacoes':'Acervo inicial de dois estudos históricos; não corresponde a todas as publicações Sebrae. Resultados de pesquisa não são normas tributárias nem cadastro censitário atual. Sobrevivência: empresas criadas 2015–2019, verificadas no final de 2020; entrevistas sobretudo dez/2020–jan/2021. Pulso: pesquisa online 24/04–02/05/2023. Revisão humana das tabelas e páginas sem texto permanece explícita.','estudos':results}
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'indice.md','# Estudos públicos Sebrae\n\n'+report['limitacoes']+'\n\n'+'\n'.join(f'- [{r["titulo"]}]({r["markdown"]}) — {r["paginas"]} páginas, estado {r["status"]}' if 'markdown' in r else f'- {r["source_id"]}: erro — {r["erro"]}' for r in results)+'\n')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);p.add_argument('--source',choices=[*SOURCES,'all'],default='all');args=p.parse_args()
    with httpx.Client(timeout=90,follow_redirects=True) as client:r=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client)
    return int(any(s['status']!='extraido' for s in r['estudos']))
if __name__=='__main__':raise SystemExit(main())
