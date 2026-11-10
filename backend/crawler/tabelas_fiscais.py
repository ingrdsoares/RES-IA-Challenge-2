"""Snapshots oficiais de tabelas fiscais; não determina aplicação tributária."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from defusedxml import ElementTree as ET
from .anexos import _cell, _write_atomic

SOURCES = {
 'ncm': ('https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json', 'JSON corrente Siscomex; inclui níveis hierárquicos. Não inclui histórico completo nem códigos futuros.'),
 'cfop': ('https://www.confaz.fazenda.gov.br/legislacao/ajustes/2024/AJ003_24', 'Anexo do Ajuste SINIEF 03/24 e retificações na página. Snapshot documental; não consolida alterações posteriores nem determina vigência individual.'),
 'cest': ('https://www.confaz.fazenda.gov.br/legislacao/convenios/2018/CV142_18', 'Tabelas do Convênio ICMS 142/18 na página consolidada, incluindo redações anteriores/revogadas e retificações. Registros repetidos são preservados; não usar como tabela exclusivamente vigente.'),
}
XSD_URL = 'https://dfe-portal.svrs.rs.gov.br/NFE/DownloadArquivoEstatico/?sistema=NFE&tipoArquivo=2&nomeArquivo=PL_010c_NT2022_002v1.30.zip'
NS = {'x': 'http://www.w3.org/2001/XMLSchema'}

def parse_ncm(raw):
    data = json.loads(raw.decode('utf-8-sig'))
    rows = data['Nomenclaturas']
    if not rows or any(not isinstance(r.get('Codigo'), str) or not r.get('Descricao') for r in rows):
        raise ValueError('JSON NCM sem códigos/descrições')
    return rows, {k:v for k,v in data.items() if k != 'Nomenclaturas'}

def parse_html(raw, category):
    soup = BeautifulSoup(raw, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    identity = '142/18' if category == 'cest' else '03/24'
    if identity not in soup.get_text(' ', strip=True):
        raise ValueError('Identidade da fonte não encontrada')
    rows = []
    if category == 'cest':
        for ti, table in enumerate(soup.find_all('table'), 1):
            for ri, tr in enumerate(table.find_all('tr'), 1):
                cells = [x.get_text(' ', strip=True) for x in tr.find_all(['td','th'], recursive=False)]
                if len(cells) >= 4 and re.fullmatch(r'\d{2}\.\d{3}\.\d{2}', cells[1]):
                    rows.append({'Codigo':cells[1], 'Descricao':cells[3], 'NCM_SH':cells[2], 'Item':cells[0], 'Tabela':ti, 'Linha':ri, 'Texto_riscado':bool(tr.find(['s','strike','del']) or tr.find(style=re.compile('line-through')))})
    else:
        # Each paragraph occurrence stays separate, including rectifications/history.
        for i, p in enumerate(soup.find_all('p'), 1):
            text = p.get_text(' ', strip=True)
            m = re.match(r'^[“"\s]*([123567]\.\d{3})\s*[-–]\s*(.+)', text)
            if m:
                rows.append({'Codigo':m[1], 'Descricao':m[2], 'Paragrafo':i, 'Texto_riscado':bool(p.find(['s','strike','del']) or p.find(style=re.compile('line-through')))})
    if not rows:
        raise ValueError('Nenhum código fiscal extraído')
    return rows, {'titulo': title}

def parse_xsd(raw, category):
    root = ET.fromstring(raw)
    rows=[]
    # ICMS is explicitly scoped by its ancestor; other taxes also use CST.
    for group in root.findall('.//x:element[@name="ICMS"]', NS):
        for e in group.findall('.//x:element', NS):
            if e.get('name') != category.upper():
                continue
            docs='\n'.join(''.join(d.itertext()) for d in e.findall('x:annotation/x:documentation', NS))
            for enum in e.findall('.//x:enumeration', NS):
                code=enum.get('value')
                # Preserve complete annotation: a shared annotation may list several codes.
                rows.append({'Codigo':code, 'Descricao':docs, 'Contexto':'ICMS', 'Anotacao_compartilhada':True})
    if not rows or any(not r['Descricao'] for r in rows):
        raise ValueError('XSD sem descrições ICMS')
    return rows, {'versao':'PL_010c_NT2022_002v1.30 / NF-e 4.00', 'tributo':'ICMS', 'natureza':'enumerações e anotações do leiaute; variantes de grupos preservadas'}

def persist(output, category, raw, extension, url, scope, rows, details):
    digest=hashlib.sha256(raw).hexdigest()
    dest=output/category/digest
    dest.mkdir(parents=True, exist_ok=True)
    original=dest/f'original.{extension}'
    original.write_bytes(raw)
    meta={'categoria':category,'url':url,'coletado_em':datetime.now(timezone.utc).isoformat(),'sha256':digest,'original':original.name,'registros':len(rows),'codigos_distintos':len({r['Codigo'] for r in rows}),'cobertura':scope,'revisao':'pendente','detalhes':details}
    _write_atomic(dest/'metadados.json',json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    _write_atomic(dest/'registros.json',json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    lines=[f'# {category.upper()}', '',f'Fonte: {url}',f'Coleta UTC: {meta["coletado_em"]}',f'SHA-256: `{digest}`','',scope,'','Os códigos não determinam, isoladamente, o tratamento tributário. Conferir norma, vigência e contexto da operação. Descrições e variantes da fonte são preservadas; não houve consolidação jurídica.','','| Código | Descrição/anotação original | Outros campos |','| --- | --- | --- |']
    for r in rows:
        extra={k:v for k,v in r.items() if k not in ('Codigo','Descricao')}
        lines.append('| '+ ' | '.join(_cell(v) for v in [r['Codigo'],r['Descricao'],json.dumps(extra,ensure_ascii=False)])+' |')
    _write_atomic(dest/'tabela.md','\n'.join(lines)+'\n')
    return {**meta,'arquivo':str((dest/'tabela.md').relative_to(output)).replace('\\','/')}

def collect(output):
    output=Path(output)
    manifest=[]
    with httpx.Client(timeout=120,follow_redirects=True) as client:
        for category,(url,scope) in SOURCES.items():
            response=client.get(url); response.raise_for_status()
            raw=response.content
            rows,details=parse_ncm(raw) if category=='ncm' else parse_html(raw,category)
            manifest.append(persist(output,category,raw,'json' if category=='ncm' else 'html',url,scope,rows,details))
        candidates=list((Path(__file__).parent/'data/documentos-fiscais/nfe-xsd').glob('*/original.zip'))
        if candidates:
            archive=candidates[0].read_bytes()
        else:
            response=client.get(XSD_URL); response.raise_for_status(); archive=response.content
        import io
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            member=next(n for n in z.namelist() if n.endswith('/leiauteNFe_v4.00.xsd'))
            raw=z.read(member)
        for category in ('cst','csosn'):
            rows,details=parse_xsd(raw,category)
            details.update({'arquivo_no_zip':member,'zip_sha256':hashlib.sha256(archive).hexdigest(),'zip_url':XSD_URL})
            entry=persist(output,category,raw,'xsd',XSD_URL,'ICMS da NF-e: enumerações CST (dois dígitos; origem não concatenada) ou CSOSN. Não abrange CST de outros tributos nem garante vigência atual.',rows,details)
            dest=output/category/entry['sha256']; (dest/'fonte.zip').write_bytes(archive)
            manifest.append(entry)
    _write_atomic(output/'manifesto.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    lines=['# Tabelas fiscais — índice','', 'Snapshots oficiais para pesquisa. Histórico e variantes preservados; revisão jurídica pendente.','','| Categoria | Registros | Códigos distintos | Arquivo |','| --- | --- | --- | --- |']
    lines += [f'| {e["categoria"]} | {e["registros"]} | {e["codigos_distintos"]} | [Markdown]({e["arquivo"]}) |' for e in manifest]
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    return manifest

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'data/tabelas-fiscais')
    args=parser.parse_args()
    print(json.dumps([{k:e[k] for k in ('categoria','registros','codigos_distintos')} for e in collect(args.output)],ensure_ascii=False,indent=2))
