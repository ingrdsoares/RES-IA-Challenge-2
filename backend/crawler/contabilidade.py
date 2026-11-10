"""Coleta normas contábeis simplificadas oficiais do CFC para Markdown."""

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

import httpx
from backend.crawler.anexos import _cell,_write_atomic
from backend.crawler.manuais import ingest

CATALOG_URL='https://cfc.org.br/tecnica/normas-brasileiras-de-contabilidade/normas-simplificadas-para-pmes/'
PDF_BASE='https://www1.cfc.org.br/sisweb/SRE/docs/'
SOURCES={
    'itg1000':{'title':'ITG 1000 (15/12/2022) — normas aplicáveis e modelos para microentidade e pequena empresa',
        'url':PDF_BASE+'ITG%201000.pdf','identity':['itg 1000','15 de dezembro de 2022','normas aplicaveis']},
    'nbctg1000r1':{'title':'NBC TG 1000 (R1) — Contabilidade para Pequenas e Médias Empresas',
        'url':PDF_BASE+'NBCTG1000(R1).pdf','identity':['nbc tg 1000 r1','contabilidade']},
    'nbctg1001':{'title':'NBC TG 1001 — Contabilidade para Pequenas Empresas',
        'url':PDF_BASE+'NBCTG1001.pdf','identity':['nbc tg 1001','pequenas empresas']},
    'nbctg1002':{'title':'NBC TG 1002 — Contabilidade para Microentidades',
        'url':PDF_BASE+'NBCTG1002.pdf','identity':['nbc tg 1002','microentidades']},
}
for info in SOURCES.values():
    info.update({'catalog_url':CATALOG_URL,'kind':'norma_contabil','camada':'C','publicador':'Conselho Federal de Contabilidade'})
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'contabilidade'


def collect(sources: list[str],output: Path,client: httpx.Client) -> dict:
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    for source in sources:
        info=SOURCES[source]
        try:
            response=client.get(info['url']);response.raise_for_status()
            path=ingest(source,response.content,output,source_info=info)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc:
            results.append({'source_id':source,'titulo':info['title'],'source_url':info['url'],
                            'status':'erro','erro':str(exc)})
        print(f'{source}: {results[-1]["status"]}',flush=True)
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),
            'catalog_url':CATALOG_URL,'normas':results}
    lines=['# Normas contábeis simplificadas — CFC','',f'[Catálogo oficial]({CATALOG_URL})','',
        '> Referências técnicas (camada C, conforme a taxonomia do projeto). Edição, vigência, alterações e aplicabilidade por empresa exigem revisão. Índice da última execução; versões anteriores permanecem no disco.','',
        '| Norma | Estado | Páginas | Blocos tabulares |','|---|---|---|---|']
    for item in results:
        title=_cell(item['titulo']);link=f'[{title}]({item["markdown"]})' if 'markdown' in item else title
        lines.append(f'| {link} | {item["status"]} | {item.get("paginas", "")} | {item.get("tabelas", "")} |')
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
        pending=sum(item['status']!='extraido' for item in report['normas'])
        print(f'Normas: {report["total"]}; pendências/erros: {pending}')
        print(f'Índice: {(args.output/"indice.md").resolve()}')
        return int(pending>0)
    except (ValueError,OSError) as exc:
        print(f'Falha na coleta contábil: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
