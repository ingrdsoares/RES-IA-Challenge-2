"""Indicadores anuais oficiais do IBGE/SIDRA, com recortes explícitos."""
import argparse
import hashlib
import json
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
import httpx
from .anexos import _write_atomic, _cell

SOURCES = {
    'pib': {'table': '6784', 'variables': '9808,9812', 'period': '2021-2023', 'title': 'PIB e PIB per capita — 2021 a 2023'},
    'cempre': {'table': '9509', 'variables': '367,706', 'period': '2022-2024', 'title': 'CEMPRE: empresas atuantes e unidades locais — 2022 a 2024'},
}
DEFAULT_OUTPUT = Path(__file__).resolve().parent/'data'/'ibge-indicadores'

def source_url(info):
    return f'https://apisidra.ibge.gov.br/values/t/{info["table"]}/n1/all/v/{info["variables"]}/p/{info["period"]}?formato=json'

def ingest(source, raw, output):
    info=SOURCES[source]
    records=json.loads(raw)
    if not isinstance(records,list) or len(records)<2 or not all(isinstance(r,dict) for r in records):
        raise ValueError('SIDRA não retornou cabeçalho e observações.')
    headers=records[0]; rows=records[1:]
    required={'NC','NN','MC','MN','V','D1C','D1N','D2C','D2N','D3C','D3N'}
    if not required.issubset(headers) or any(not required.issubset(r) for r in rows):
        raise ValueError('Dimensões SIDRA incompletas.')
    years=set(str(y) for y in range(int(info['period'][:4]),int(info['period'][-4:])+1))
    variables=set(info['variables'].split(','))
    if any(r['NC']!='1' or r['D1C']!='1' or r['D2C'] not in variables or r['D3C'] not in years for r in rows):
        raise ValueError('Recorte territorial, variável ou período divergente.')
    keys=[(r['D1C'],r['D2C'],r['D3C']) for r in rows]
    if len(set(keys))!=len(keys) or len(rows)!=len(years)*len(variables):
        raise ValueError('Observações duplicadas ou cobertura incompleta.')
    digest=hashlib.sha256(raw).hexdigest(); target=Path(output)/source/digest
    meta={'source_id':source,'titulo':info['title'],'source_url':source_url(info),'catalog_url':f'https://sidra.ibge.gov.br/tabela/{info["table"]}', 'publicador':'IBGE','camada':'A','tabela':info['table'],'periodos':sorted(years),'variaveis':sorted(variables),'territorio':{'nivel':'N1','codigo':'1','nome':'Brasil'},'registros':len(rows),'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),'status':'extraido','limitacoes':'Recorte nacional anual explícito; não representa todo o acervo IBGE. CEMPRE: empresas e outras organizações, não apenas pequenos negócios. Séries com metodologias distintas não são encadeadas.'}
    columns=list(headers)
    lines=[f'# {info["title"]}','',f'Fonte: {source_url(info)}',f'Tabela: {meta["catalog_url"]}',f'SHA256 do original: `{digest}`','',meta['limitacoes'],'','Valores e marcadores de ausência/sigilo preservados literalmente. Códigos, unidades e nomes estão nas colunas abaixo.','', '| '+' | '.join(_cell(headers[c]) for c in columns)+' |','|'+'---|'*len(columns)]
    lines += ['| '+' | '.join(_cell(r.get(c,'')) for c in columns)+' |' for r in rows]
    if target.exists():
        previous=json.loads((target/'metadados.json').read_text(encoding='utf-8'))
        if (target/'original.json').read_bytes()!=raw or previous['source_url']!=meta['source_url'] or previous['sha256']!=digest or not (target/'indicadores.md').is_file():
            raise ValueError('Snapshot inconsistente.')
        return target/'indicadores.md'
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.coleta-',dir=target.parent))
    try:
        (staging/'original.json').write_bytes(raw)
        for name,data in [('metadados.json',json.dumps(meta,ensure_ascii=False,indent=2)),('indicadores.md','\n'.join(lines)+'\n')]: _write_atomic(staging/name,data)
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return target/'indicadores.md'

def collect(sources,output,client):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);results=[]
    for source in sources:
        try:
            response=client.get(source_url(SOURCES[source]));response.raise_for_status()
            path=ingest(source,response.content,output)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc: results.append({'source_id':source,'status':'erro','erro':str(exc)})
        print(source,results[-1]['status'],flush=True)
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'indicadores':results}
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'indice.md','# Indicadores IBGE/SIDRA\n\n'+'\n'.join(f'- [{r["source_id"]}]({r["markdown"]}) — {r["registros"]} observações' if 'markdown' in r else f'- {r["source_id"]}: erro — {r["erro"]}' for r in results)+'\n')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);p.add_argument('--source',choices=[*SOURCES,'all'],default='all');args=p.parse_args()
    with httpx.Client(timeout=60,follow_redirects=True) as client:report=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client)
    return int(any(r['status']=='erro' for r in report['indicadores']))
if __name__=='__main__':raise SystemExit(main())
