"""Coleta mensal da agenda tributária federal e orientações declaratórias."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote,urljoin,urlsplit

from bs4 import BeautifulSoup
import httpx

from backend.crawler.anexos import _cell,_write_atomic
from backend.crawler.paginas import ingest,normalize

BASE='https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria'
MONTHS=['janeiro','fevereiro','marco','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'obrigacoes'
SERVICES={
    'pgdas':{'title':'Orientações oficiais PGDAS-D','url':'https://www.gov.br/pt-br/servicos/declarar-apuracoes-mensais-do-simples-nacional','identity':['PGDAS-D']},
    'defis':{'title':'Orientações oficiais DEFIS','url':'https://www.gov.br/pt-br/servicos/declarar-apuracoes-e-informacoes-anuais-do-simples-nacional','identity':['DEFIS']},
    'dasn-simei':{'title':'Orientações oficiais DASN-SIMEI','url':'https://www.gov.br/pt-br/servicos/declarar-receita-bruta-anual-para-o-mei','identity':['DASN']},
}


def _period(period: str) -> tuple[int,int]:
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',period):raise ValueError('Período deve ser AAAA-MM.')
    return int(period[:4]),int(period[-2:])


def discover_month(raw: bytes, annual_url: str, period: str) -> str:
    _,month=_period(period)
    soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser')
    body=soup.select_one('#content-core')
    if body is None:raise ValueError('Índice anual sem conteúdo reconhecível.')
    for link in body.find_all('a',href=True):
        url=urljoin(annual_url,link['href'])
        parsed=urlsplit(url)
        if (parsed.netloc==urlsplit(annual_url).netloc
                and parsed.path.rstrip('/').startswith(urlsplit(annual_url).path.rstrip('/')+'/')
                and normalize(unquote(parsed.path.rstrip('/').split('/')[-1]))==MONTHS[month-1]):
            return url
    raise ValueError('Mês solicitado ainda não foi encontrado no índice oficial.')


def discover_days(raw: bytes, month_url: str, period: str) -> list[str]:
    year,month=_period(period)
    soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser');body=soup.select_one('#content-core')
    if body is None:raise ValueError('Página mensal sem conteúdo reconhecível.')
    result=[]
    parent=urlsplit(month_url)
    for link in body.find_all('a',href=True):
        url=urljoin(month_url,link['href']);parsed=urlsplit(url)
        prefix=unquote(parent.path.rstrip('/'))+'/'
        path=unquote(parsed.path).rstrip('/')
        if parsed.netloc!=parent.netloc or not path.startswith(prefix):continue
        slug=path[len(prefix):]
        match=re.fullmatch(r'dia[- ](\d{2})-(\d{2})-(\d{4})',slug,re.I)
        allowed=slug in ('diario','outros-vencimentos')
        if match and int(match[2])==month and int(match[3])==year:
            datetime(year,month,int(match[1]));allowed=True
        if allowed and url not in result:result.append(url)
    if not result:raise ValueError('Nenhuma página diária/recorrente encontrada no mês.')
    return result


def collect(period: str, output: Path, client: httpx.Client) -> dict:
    year,month=_period(period)
    root=Path(output)/period;root.mkdir(parents=True,exist_ok=True)
    results=[];queue=[]
    annual=BASE+'/'+str(year)
    try:
        response=client.get(annual);response.raise_for_status()
        queue.append(('agenda-indice',{'title':f'Índice da agenda federal {year}','url':annual,'identity':[str(year)],'camada':'A','kind':'agenda_indice','periodo':period},response.content))
        monthly=discover_month(response.content,annual,period)
        response=client.get(monthly);response.raise_for_status()
        queue.append(('agenda-mes',{'title':f'Agenda federal {period}','url':monthly,'identity':[f'{MONTHS[month-1]} de {year}'],'camada':'A','kind':'agenda_mes','periodo':period},response.content))
        for number,url in enumerate(discover_days(response.content,monthly,period),1):
            match=re.search(r'(\d{2})-(\d{2})-(\d{4})$',unquote(url))
            date=datetime(int(match[3]),int(match[2]),int(match[1])).date().isoformat() if match else None
            identity=[f'{match[1]}/{match[2]}/{match[3]}'] if match else (['diario'] if url.rstrip('/').endswith('/diario') else ['vencimentos'])
            queue.append((f'agenda-pagina-{number:02d}',{'title':f'Agenda {date or period} — {unquote(url.split("/")[-1])}',
                'url':url,'identity':identity,'camada':'A','kind':'agenda_diaria','periodo':period,'data_publicada':date},None))
    except (httpx.HTTPError,ValueError) as exc:
        results.append({'source_id':'agenda-descoberta','titulo':'Descoberta da agenda','status':'erro','erro':str(exc)})
    queue.extend((key,{**info,'camada':'B','kind':'orientacao_declaracao'},None) for key,info in SERVICES.items())
    for source,info,raw in queue:
        try:
            if raw is None:
                response=client.get(info['url']);response.raise_for_status();raw=response.content
            path=ingest(source,info,raw,root)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(root).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc:
            results.append({'source_id':source,'titulo':info['title'],'source_url':info['url'],'status':'erro','erro':str(exc)})
        print(f'{source}: {results[-1]["status"]}',flush=True)
    refs=[]
    for item in results:
        if 'markdown' not in item or item.get('tipo')!='agenda_diaria':continue
        path=root/item['markdown'];tables=json.loads((path.parent/'tabelas.json').read_text(encoding='utf-8'))
        for table in tables:
            for row in table['linhas']:
                text=' | '.join(c['texto'] for c in row['celulas'])
                tags=[tag for tag in ['simples nacional','simei','pgdas','dasn','defis'] if tag in normalize(text)]
                if tags:refs.append({'source_id':item['source_id'],'source_url':item['source_url'],
                    'data_pagina':item['data_publicada_no_titulo'],'tabela':table['numero'],'linha':row['numero'],
                    'texto_literal':text,'termos_detectados':tags,'aplicabilidade':'nao_avaliada','markdown':item['markdown']})
    report={'periodo':period,'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'fontes':results,
            'referencias_por_palavra_chave':len(refs)}
    lines=[f'# Obrigações e agenda tributária — {period}','','> Recorte documental federal. Não conclui exigibilidade por empresa, não gera alertas e não extrapola datas para outros períodos. Índice da última execução.','',
        '| Fonte | Estado | Tabelas | Linhas literais |','|---|---|---|---|']
    for item in results:
        title=_cell(item['titulo']);link=f'[{title}]({item["markdown"]})' if 'markdown' in item else title
        lines.append(f'| {link} | {item["status"]} | {item.get("tabelas", "")} | {item.get("linhas_tabelas", "")} |')
    lines.extend(['','## Referências para revisão','','Linhas com termos Simples Nacional, SIMEI, PGDAS, DASN ou DEFIS. A seleção não é exaustiva e não determina aplicabilidade.','','| Data da página | Tabela / linha | Texto literal |','|---|---|---|'])
    for ref in refs:lines.append(f'| {ref["data_pagina"] or "sem dia específico"} | [{ref["tabela"]} / {ref["linha"]}]({ref["markdown"]}) | {_cell(ref["texto_literal"])} |')
    for item in results:
        if 'erro' in item:lines.extend(['',f'> Falha em {item["source_id"]}: {_cell(item["erro"])}'])
    _write_atomic(root/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(root/'referencias.json',json.dumps(refs,ensure_ascii=False,indent=2))
    _write_atomic(root/'indice.md','\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--periodo',default='2026-11',help='AAAA-MM; padrão deste recorte: 2026-11.')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    try:
        with httpx.Client(timeout=45,follow_redirects=True,headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client:
            report=collect(args.periodo,args.output,client)
        pending=sum(i['status']!='extraido' for i in report['fontes'])
        print(f'Fontes: {report["total"]}; pendências/erros: {pending}; referências: {report["referencias_por_palavra_chave"]}')
        print(f'Índice: {(args.output/args.periodo/"indice.md").resolve()}')
        return int(pending>0)
    except (httpx.HTTPError,ValueError,OSError) as exc:
        print(f'Falha na coleta de obrigações: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
