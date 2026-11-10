"""Agenda federal publicada de 2026 e calendário administrativo federal/DF documentado."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import httpx

from backend.crawler import obrigacoes
from backend.crawler.anexos import _cell, _write_atomic
from backend.crawler.paginas import ingest, normalize, parse_page

DEFAULT_OUTPUT = Path(__file__).resolve().parent/'data'/'calendario-df'
SCOPE = {'DF':'Administração direta, autárquica e fundacional do Distrito Federal; serviços essenciais ressalvados',
         'federal':'Administração pública federal direta, autárquica e fundacional; serviços essenciais ressalvados'}
SOURCES = {
 'federal-portaria-11460': {'url':'https://www.in.gov.br/web/dou/-/portaria-mgi-n-11.460-de-29-de-dezembro-de-2025-678388627','identity':['11.460','2026'],'esfera':'federal','content_selector':'.texto-dou'},
 'federal-inpi-alteracao': {'url':'https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/ponto-facultativo-do-dia-do-servidor-sera-em-30-de-outubro','identity':['8.821','30 de outubro de 2026'],'esfera':'federal','content_selector':'#content-core'},
 'df-lei-963': {'url':'https://www.sinj.df.gov.br/sinj/norma/48922/lei_963_04_12_1995.html','identity':['963','30 de novembro'],'esfera':'DF','content_selector':'#div_texto','escopo':'Distrito Federal; feriado local instituído por lei'},
 'federal-portaria-8821': {'url':'https://www.in.gov.br/web/dou/-/portaria-mgi-n-8.821-de-26-de-outubro-de-2026-740421653','identity':['8.821','30 de outubro'],'esfera':'federal','content_selector':'.texto-dou'},
 'df-decreto-48117': {'url':'https://www.sinj.df.gov.br/sinj/Norma/dd13897d3d894936940fbd58e2161541/exec_dec_48117_2025.html','identity':['48.117','2026'],'esfera':'DF','content_selector':'#div_texto'},
 'df-decreto-49585': {'url':'https://www.sinj.df.gov.br/sinj/Norma/4d2fcfe819214d91b01b4ee6f326182f/exec_dec_49585_2026.html','identity':['49.585','30 de outubro'],'esfera':'DF','content_selector':'#div_texto'},
 'df-decreto-48448': {'url':'https://www.sinj.df.gov.br/sinj/Norma/106f9c1e0c7148e4867b7ecf44b79e41/Decreto_48448_01_04_2026.html','identity':['48.448','2026'],'esfera':'DF','content_selector':'#div_texto'},
 'df-decreto-48831': {'url':'https://www.sinj.df.gov.br/sinj/Norma/93b6ac3f7a0b488c807b995357735f0a/Decreto_48831_25_06_2026.html','identity':['48.831','29 de junho'],'esfera':'DF','content_selector':'#div_texto'},
 'federal-calendario-mgi': {'url':'https://www.gov.br/gestao/pt-br/assuntos/noticias/2025/dezembro/confira-o-calendario-oficial-de-feriados-nacionais-e-pontos-facultativos-em-2026','identity':['11.460','2026'],'esfera':'federal','content_selector':'#content-core'},
}


for _source_id, _info in SOURCES.items():
    _info['camada']='A' if any(kind in _source_id for kind in ('-lei-','-decreto-','-portaria-')) else 'B'


def set_layer(path, layer):
    """Correct classification without changing the source snapshot or collection date."""
    meta_path=path.parent/'metadados.json'
    meta=json.loads(meta_path.read_text(encoding='utf8'))
    if meta.get('camada')!=layer:
        text=path.read_text(encoding='utf8')
        text=re.sub(r'^camada: [AB]$',f'camada: {layer}',text,count=1,flags=re.M)
        meta['camada']=layer
        _write_atomic(path,text)
        _write_atomic(meta_path,json.dumps(meta,ensure_ascii=False,indent=2))
    return meta


def correct_existing_layers(output):
    output=Path(output)
    for source,layer in [('agenda-indice-2026','A')]+[(key,info['camada']) for key,info in SOURCES.items()]:
        for path in (output/source).glob('*/pagina.md'): set_layer(path,layer)
    manifest=output/'manifesto.json'
    if manifest.exists():
        report=json.loads(manifest.read_text(encoding='utf8'))
        for item in report['fontes']:
            if 'markdown' in item: item['camada']=json.loads((output/item['markdown']).with_name('metadados.json').read_text(encoding='utf8'))['camada']
        _write_atomic(manifest,json.dumps(report,ensure_ascii=False,indent=2))
    receipt=output/'integridade.json'
    if receipt.exists():
        data=json.loads(receipt.read_text(encoding='utf8'))
        for key in data: data[key]=hashlib.sha256((output/key).read_bytes()).hexdigest()
        _write_atomic(receipt,json.dumps(data,indent=2))


def published_months(raw, year=2026):
    annual=obrigacoes.BASE+'/'+str(year)
    result={}
    for month in range(1,13):
        period=f'{year}-{month:02d}'
        try: result[period]=obrigacoes.discover_month(raw,annual,period)
        except ValueError as exc:
            if 'ainda não' not in str(exc): raise
    return result


def calendar_rows(raw, source, info):
    soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser')
    body=soup.select_one(info.get('content_selector','body')) or soup
    for node in body.select('s, strike, del, script, style'): node.decompose()
    rows=[]
    for unit,node in enumerate(body.find_all(['p','li']),1):
        text=' '.join(t.strip() for t in node.find_all(string=True) if t.find_parent(['p','li']) is node and t.strip())
        norm=normalize(text)
        if not ('ponto facultativo' in norm or 'feriado' in norm): continue
        # Date must be explicitly written as a day and month, never inferred from a weekday.
        match=re.search(r'\b(\d{1,2})(?:º|°|o)?\s+de\s+('+'|'.join(obrigacoes.MONTHS)+r')\b',norm)
        if not match: continue
        day,month=int(match[1]),obrigacoes.MONTHS.index(match[2])+1
        # The commemorated date in an amendment supersedes the historical heading date.
        shifted=re.search(r'comemorado(?: excepcionalmente)? no dia (\d{1,2}) de ('+'|'.join(obrigacoes.MONTHS)+r')',norm)
        if not shifted and not (match.start()<12 or 'feriado no dia' in norm[:match.start()] or 'fica estabelecido o dia' in norm[:match.start()]): continue
        if shifted: day,month=int(shifted[1]),obrigacoes.MONTHS.index(shifted[2])+1
        try: normalized=date(2026,month,day).isoformat()
        except ValueError: raise ValueError('Data impossível no calendário oficial; revisão necessária.')
        category=('horario_reduzido' if re.search(r'ponto facultativo (?:ate|apos)',norm) else
                  'ponto_facultativo' if 'ponto facultativo' in norm else 'feriado')
        rows.append({'data':normalized,'categoria':category,'esfera':info['esfera'],
                     'escopo':info.get('escopo',SCOPE[info['esfera']]),'source_id':source,'source_url':info['url'],
                     'unidade':node.get('linkname',f'paragrafo-ou-item-{unit}'),'trecho_literal':text,
                     'estado_documental':('superado_por_portaria_mgi_8821_2026' if source in ('federal-calendario-mgi','federal-portaria-11460') and normalized=='2026-10-28' else 'exige_revisao'),
                     'revisao_humana':'pendente','aplicacao_empresa_privada':'nao_avaliada',
                     'deslocamento_vencimento_fiscal':'nao_inferido'})
    return rows


def validated_manifest(root):
    manifest=root/'manifesto.json'
    if not manifest.exists(): return None
    report=json.loads(manifest.read_text(encoding='utf-8'))
    if any(x.get('status')!='extraido' for x in report['fontes']): return None
    receipt_path=root/'integridade.json'
    receipt=json.loads(receipt_path.read_text(encoding='utf8')) if receipt_path.exists() else {}
    artifacts={}; damaged=False; expected_refs=[]
    for item in report['fontes']:
        if 'markdown' not in item: continue
        folder=(root/item['markdown']).parent
        raw=(folder/'original.html').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError(f'Cache corrompido: {folder}')
        info={'url':item['source_url'],'title':item['titulo'],'identity':[],
              'kind':item.get('tipo'),'periodo':item.get('periodo_agenda'),
              'data_publicada':item.get('data_publicada_no_titulo'),'camada':item.get('camada')}
        parsed=parse_page(raw,info)
        if item.get('tipo')=='agenda_diaria':
            for table in parsed['tabelas']:
                for row in table['linhas']:
                    text=' | '.join(c['texto'] for c in row['celulas'])
                    tags=[tag for tag in ['simples nacional','simei','pgdas','dasn','defis'] if tag in normalize(text)]
                    if tags: expected_refs.append({'source_id':item['source_id'],'source_url':item['source_url'],
                        'data_pagina':item['data_publicada_no_titulo'],'tabela':table['numero'],'linha':row['numero'],
                        'texto_literal':text,'termos_detectados':tags,'aplicabilidade':'nao_avaliada','markdown':item['markdown']})
        valid=True
        try:
            md=(folder/'pagina.md').read_text(encoding='utf8')
            valid=(md.endswith(parsed['markdown']+'\n') and item['source_url'] in md
                   and json.loads((folder/'tabelas.json').read_text(encoding='utf8'))==parsed['tabelas'])
            for name in ['pagina.md','tabelas.json','metadados.json']:
                path=folder/name;key=path.relative_to(root).as_posix()
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                if key in receipt and receipt[key]!=digest: valid=False
                artifacts[key]=digest
        except (OSError,ValueError): valid=False
        if not valid:
            # Rebuild derived artifacts from verified originals; original versions remain intact.
            with tempfile.TemporaryDirectory(dir=root) as temp:
                rebuilt=ingest(item['source_id'],info,raw,Path(temp))
                for name in ['pagina.md','tabelas.json','metadados.json']:
                    _write_atomic(folder/name,(rebuilt.parent/name).read_text(encoding='utf8'))
            damaged=True
    for name in ['referencias.json','indice.md']:
        path=root/name
        try:
            raw=path.read_bytes()
            if name.endswith('.json') and json.loads(raw)!=expected_refs: raise ValueError('Referências inválidas')
            if name.endswith('.md') and not raw.startswith(b'# '): raise ValueError('Índice inválido')
            digest=hashlib.sha256(raw).hexdigest()
            if name in receipt and receipt[name]!=digest: damaged=True
            artifacts[name]=digest
        except (OSError,ValueError): damaged=True
    if damaged: return None
    _write_atomic(receipt_path,json.dumps(artifacts,indent=2))
    return report


class CachedClient:
    """Reuse only verified original bytes; retain the existing monthly collector."""
    def __init__(self,client,cache): self.client,self.cache=client,cache
    def get(self,url):
        if url in self.cache:
            return httpx.Response(200,content=self.cache[url],request=httpx.Request('GET',url))
        response=self.client.get(url);response.raise_for_status()
        self.cache[url]=response.content
        return response


def collect(output,client,existing=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    existing=Path(existing or obrigacoes.DEFAULT_OUTPUT)
    cache={};results=[];rows=[];months=[]
    # November and service guidance already collected elsewhere remain referenced.
    for meta_path in [*existing.glob('*/*/*/metadados.json'), *(output/'obrigacoes').glob('*/*/*/metadados.json')]:
        meta=json.loads(meta_path.read_text(encoding='utf-8'))
        raw=(meta_path.parent/'original.html').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=meta['sha256']: raise ValueError(f'Cache corrompido: {meta_path}')
        if meta.get('tipo')!='agenda_indice': cache[meta['source_url']]=raw
    wrapped=CachedClient(client,cache)
    annual=obrigacoes.BASE+'/2026'
    try:
        response=wrapped.get(annual);response.raise_for_status()
        available=published_months(response.content)
        index_path=ingest('agenda-indice-2026',{'url':annual,'title':'Índice anual federal 2026','identity':['2026'],'camada':'A'},response.content,output)
        results.append({**set_layer(index_path,'A'),'markdown':index_path.relative_to(output).as_posix()})
        for n in range(1,13):
            period=f'2026-{n:02d}'
            if period not in available:
                months.append({'periodo':period,'status':'nao_encontrado_no_indice','source_url':annual,
                               'observacao':'Ausência de link no índice oficial; não afirma indisponibilidade definitiva.'});continue
            target=existing/period if (existing/period/'manifesto.json').exists() else output/'obrigacoes'/period
            try:
                report=validated_manifest(target)
                if report is None:
                    report=obrigacoes.collect(period,output/'obrigacoes',wrapped);target=output/'obrigacoes'/period
                    validated_manifest(target)
            except (httpx.HTTPError,ValueError,OSError) as exc:
                months.append({'periodo':period,'status':'erro','erro':str(exc),'source_url':available[period]})
                continue
            months.append({'periodo':period,'status':'extraido' if all(x['status']=='extraido' for x in report['fontes']) else 'pendente',
                           'manifesto':str((target/'manifesto.json').resolve()),'referencias':str((target/'referencias.json').resolve()),
                           'referencias_por_palavra_chave':report['referencias_por_palavra_chave'],'reutilizado':target.parent==existing})
    except (httpx.HTTPError,ValueError,OSError) as exc:
        results.append({'source_id':'agenda-descoberta-2026','source_url':annual,'status':'erro','erro':str(exc)})
    for source,info in SOURCES.items():
        try:
            response=wrapped.get(info['url']);response.raise_for_status();raw=response.content
            path=ingest(source,{**info,'title':source},raw,output);digest=hashlib.sha256(raw).hexdigest()
            meta=set_layer(path,info['camada'])
            results.append({**meta,'sha256_transporte':digest,'markdown':path.relative_to(output).as_posix()})
            rows.extend(calendar_rows(raw,source,info))
        except (httpx.HTTPError,ValueError,OSError) as exc:
            results.append({'source_id':source,'source_url':info['url'],'status':'erro','erro':str(exc)})
    report={'ano':2026,'coletado_em':datetime.now(timezone.utc).isoformat(),'fontes':results,'meses':months,'datas':len(rows),
            'limites':'Inclui versões documentais, inclusive comunicado MGI anterior à alteração de outubro; consultar estado_documental de cada linha. Recorte documental; pontos facultativos administrativos não são automaticamente aplicáveis a empresas privadas. Não desloca prazos fiscais. Alterações exigem revisão humana.'}
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'datas.json',json.dumps(rows,ensure_ascii=False,indent=2))
    lines=['# Agenda 2026 e calendário administrativo federal / DF','',report['limites'],'','| Data | Esfera | Categoria | Estado documental | Unidade | Trecho literal |','|---|---|---|---|---|---|']
    lines += [f'| {r["data"]} | {r["esfera"]} | {r["categoria"]} | {r["estado_documental"]} | [{r["unidade"]}]({r["source_url"]}) | {_cell(r["trecho_literal"])} |' for r in rows]
    lines += ['','## Competências federais','']+[f'- {m["periodo"]}: {m["status"]}'+(f' — {m["manifesto"]}' if 'manifesto' in m else '') for m in months]
    lines += ['','## Fontes','']+[f'- [{i["source_id"]}]({i["source_url"]}): {i["status"]}'+(f' — {i["erro"]}' if 'erro' in i else '') for i in results]
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    with httpx.Client(timeout=45,follow_redirects=True,headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client: report=collect(args.output,client)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return int(any(i['status']=='erro' for i in report['fontes']) or any(m['status'] in ('pendente','erro') for m in report['meses']))

if __name__=='__main__': raise SystemExit(main())
