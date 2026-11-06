"""Coleta inicial das normas e do cronograma da reforma tributária."""

import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from bs4 import BeautifulSoup
import httpx
from backend.crawler.anexos import _cell,_write_atomic
from backend.crawler.legislacao import SOURCES as LAW_SOURCES,ingest as ingest_law
from backend.crawler.paginas import ingest as ingest_page

SOURCES={
    'ec132':{**LAW_SOURCES['ec132'],'kind':'norma'},
    'lc214':{**LAW_SOURCES['lc214'],'kind':'norma'},
    'cronograma':{'title':'Cronograma dos documentos fiscais eletrônicos — RTC',
        'url':'https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/reforma-tributaria-do-consumo/orientacoes-da-reforma-tributaria/cronograma',
        'identity':['cronograma','documentos fiscais'],'camada':'B','kind':'cronograma_rtc'},
}
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'reforma'


def collect(sources: list[str],output: Path,client: httpx.Client) -> dict:
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    for source in sources:
        info=SOURCES[source]
        try:
            response=client.get(info['url']);response.raise_for_status();raw=response.content
            if info['kind']=='norma':
                path=ingest_law(source,raw,output)
                markdown=path.read_text(encoding='utf-8')
                soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser')
                content=soup.select_one(info['content_selector']) if info.get('content_selector') else soup
                meta={'source_id':source,'titulo':info['title'],'source_url':info['url'],
                    'visao':info['view'],'camada':'A','sha256':hashlib.sha256(raw).hexdigest(),
                    'coletado_em':re.search(r'^coletado_em: (.+)$',markdown,re.M).group(1),
                    'cabecalhos_artigo':len(re.findall(r'^## Art\.',markdown,re.M)),
                    'tabelas_html':len(content.find_all('table')),'status':'extraido',
                    'vigencia':'nao_verificada','revisao_humana':'pendente'}
                _write_atomic(path.parent/'metadados.json',json.dumps(meta,ensure_ascii=False,indent=2))
            else:
                path=ingest_page(source,info,raw,output)
                meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc:
            results.append({'source_id':source,'titulo':info['title'],'source_url':info['url'],
                            'status':'erro','erro':str(exc)})
        print(f'{source}: {results[-1]["status"]}',flush=True)
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'fontes':results}
    lines=['# Reforma tributária — coleta inicial','',
        '> EC 132 em publicação original, LC 214 em texto atualizado da Câmara e cronograma informativo da Receita. Revisão de vigência, efeitos e compatibilidade pendente. Índice da última execução.','',
        '| Fonte | Estado | Visão | Cabeçalhos de artigo | Tabelas |','|---|---|---|---|---|']
    for item in results:
        title=_cell(item['titulo']);link=f'[{title}]({item["markdown"]})' if 'markdown' in item else title
        lines.append(f'| {link} | {item["status"]} | {item.get("visao", "pagina de orientacao")} | {item.get("cabecalhos_artigo", "")} | {item.get("tabelas_html", item.get("tabelas", ""))} |')
    lines.extend(['','Cabeçalhos reconhecidos em normas alteradoras podem incluir artigos de outras normas citadas. Não representam contagem de artigos próprios nem reconstrução consolidada da Constituição. Datas do cronograma não são convertidas em regras por empresa.'])
    for item in results:
        if 'erro' in item:lines.extend(['',f'> Falha em {item["source_id"]}: {_cell(item["erro"])}'])
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=[*SOURCES,'all'],default='all')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    try:
        with httpx.Client(timeout=60,follow_redirects=True,headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client:
            report=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client)
        errors=sum(item['status']=='erro' for item in report['fontes'])
        print(f'Fontes: {report["total"]}; erros: {errors}')
        print(f'Índice: {(args.output/"indice.md").resolve()}')
        return int(errors>0)
    except (ValueError,OSError) as exc:
        print(f'Falha na coleta da reforma: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
