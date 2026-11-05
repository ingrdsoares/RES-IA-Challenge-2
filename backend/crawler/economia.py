"""Coleta séries SGS de contexto econômico em JSON e Markdown."""

import argparse
from datetime import date,datetime,timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

import httpx
from backend.crawler.anexos import _write_atomic

SOURCES={
    'selic-meta':{'codigo':432,'titulo':'Meta da taxa Selic definida pelo Copom',
        'unidade':'percentual ao ano','periodicidade':'diaria','produtor':'BCB / Copom',
        'metadata_url':'https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom'},
    'ipca':{'codigo':433,'titulo':'IPCA — variação percentual mensal',
        'unidade':'variacao percentual mensal','periodicidade':'mensal','produtor':'IBGE',
        'metadata_url':'https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarSeries&series=433'},
}
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'economia'


def _window(start: date,end: date) -> None:
    if start>end or (end-start).days>3650:
        raise ValueError('Intervalo deve ser crescente e ter no máximo 3.650 dias.')


def _request(source: str,start: date,end: date) -> httpx.Request:
    _window(start,end)
    return httpx.Request('GET',f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SOURCES[source]["codigo"]}/dados',
        params={'formato':'json','dataInicial':start.strftime('%d/%m/%Y'),'dataFinal':end.strftime('%d/%m/%Y')})


def parse_series(source: str,raw: bytes,start: date,end: date) -> list[dict]:
    _window(start,end)
    data=json.loads(raw)
    if not isinstance(data,list) or not data:raise ValueError('Série deve conter uma lista não vazia de observações.')
    records,seen,months=[],set(),set()
    for item in data:
        if not isinstance(item,dict):raise ValueError('Observação inválida na série.')
        raw_date,value=item.get('data'),item.get('valor')
        if not isinstance(raw_date,str) or not re.fullmatch(r'\d{2}/\d{2}/\d{4}',raw_date):
            raise ValueError('Data SGS deve estar em DD/MM/AAAA.')
        day=datetime.strptime(raw_date,'%d/%m/%Y').date()
        if not start<=day<=end or day in seen:raise ValueError('Data fora da consulta ou duplicada.')
        if not isinstance(value,str) or not re.fullmatch(r'-?\d+(?:\.\d+)?',value) or not Decimal(value).is_finite():
            raise ValueError('Valor SGS deve ser decimal finito, sem separador de milhares.')
        if SOURCES[source]['periodicidade']=='mensal':
            month=day.strftime('%Y-%m')
            if month in months:raise ValueError('Mais de uma observação na mesma referência mensal.')
            months.add(month)
        seen.add(day)
        records.append({'data':day.isoformat(),'data_original':raw_date,'valor':value})
    return sorted(records,key=lambda row:row['data'])


def ingest(source: str,raw: bytes,output: Path,start: date,end: date) -> Path:
    records=parse_series(source,raw,start,end)
    info=SOURCES[source]
    digest=hashlib.sha256(raw).hexdigest()
    target=Path(output)/source/f'{start.isoformat()}_{end.isoformat()}'/digest
    result=target/'serie.md'
    if target.exists():
        meta=json.loads((target/'metadados.json').read_text(encoding='utf-8'))
        if ((target/'original.json').read_bytes()!=raw or not result.is_file() or not (target/'registros.json').is_file()
                or meta['codigo_sgs']!=info['codigo'] or meta['sha256']!=digest):
            raise ValueError('Versão existente incompleta ou divergente.')
        return result
    meta={'source_id':source,'titulo':info['titulo'],'codigo_sgs':info['codigo'],
        'source_url':str(_request(source,start,end).url),'metadata_url':info['metadata_url'],
        'camada':'A','produtor':info['produtor'],'disseminador':'Banco Central do Brasil / SGS',
        'unidade':info['unidade'],'periodicidade':info['periodicidade'],
        'inicio_solicitado':start.isoformat(),'fim_solicitado':end.isoformat(),
        'primeira_observacao':records[0]['data'],'ultima_observacao':records[-1]['data'],
        'registros':len(records),'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),
        'status':'extraido','revisao_humana':'pendente'}
    lines=['---',f'source_id: {source}',f'codigo_sgs: {info["codigo"]}',f'source_url: {meta["source_url"]}',
        'camada: A',f'unidade: {info["unidade"]}',f'periodicidade: {info["periodicidade"]}',
        f'coletado_em: {meta["coletado_em"]}',f'sha256: {digest}',f'registros: {len(records)}','---','',
        f'# {info["titulo"]}','','[JSON original](original.json) · [Registros](registros.json) · [Metadados](metadados.json)','',
        f'Produtor: {info["produtor"]}. Disseminação: Banco Central do Brasil / SGS.',
        f'Unidade: {info["unidade"]}. Periodicidade: {info["periodicidade"]}.',
        f'Intervalo solicitado: {start.isoformat()} a {end.isoformat()}.',
        f'Observações retornadas: {records[0]["data"]} a {records[-1]["data"]}.','',
        '> Valores originais preservados como decimais textuais, sem arredondamento. Lacunas não são preenchidas. A data de referência da série não é uma data de divulgação. Meta Selic não é a taxa efetiva diária; o IPCA desta série é mensal, sem cálculo de acumulado.','',
        '| Data de referência | Valor original |','|---|---|']
    lines.extend(f'| {row["data"]} | {row["valor"]} |' for row in records)
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.coleta-',dir=target.parent))
    try:
        (staging/'original.json').write_bytes(raw)
        (staging/'serie.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        (staging/'registros.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        (staging/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return result


def collect(sources: list[str],output: Path,client: httpx.Client,start: date,end: date) -> dict:
    _window(start,end)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    for source in sources:
        try:
            request=_request(source,start,end)
            response=client.get(str(request.url));response.raise_for_status()
            path=ingest(source,response.content,output,start,end)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc:
            results.append({'source_id':source,'titulo':SOURCES[source]['titulo'],'status':'erro','erro':str(exc)})
        print(f'{source}: {results[-1]["status"]}',flush=True)
    report={'inicio_solicitado':start.isoformat(),'fim_solicitado':end.isoformat(),
        'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'series':results}
    lines=['# Contexto econômico — séries oficiais SGS','',f'Consulta: {start.isoformat()} a {end.isoformat()}.','',
        '> Índice da última execução. As séries têm periodicidades e unidades distintas. Valores ausentes e períodos ainda não publicados não são estimados.','',
        '| Série | Estado | Observações | Primeira referência | Última referência |','|---|---|---|---|---|']
    for item in results:
        title=item['titulo'];link=f'[{title}]({item["markdown"]})' if 'markdown' in item else title
        lines.append(f'| {link} | {item["status"]} | {item.get("registros", "")} | {item.get("primeira_observacao", "")} | {item.get("ultima_observacao", "")} |')
    for item in results:
        if 'erro' in item:lines.extend(['',f'> Falha em {item["source_id"]}: {item["erro"]}'])
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inicio',type=date.fromisoformat,default=date(2025,1,1))
    parser.add_argument('--fim',type=date.fromisoformat,default=date(2026,11,3))
    parser.add_argument('--source',choices=[*SOURCES,'all'],default='all')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    try:
        with httpx.Client(timeout=45,follow_redirects=True,headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client:
            report=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client,args.inicio,args.fim)
        errors=sum(s['status']=='erro' for s in report['series'])
        print(f'Séries: {report["total"]}; erros: {errors}')
        print(f'Índice: {(args.output/"indice.md").resolve()}')
        return int(errors>0)
    except (ValueError,OSError) as exc:
        print(f'Falha na coleta econômica: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
