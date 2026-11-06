"""Coleta páginas Gov.br para Markdown com tabelas literais e rastreabilidade."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unicodedata
from urllib.parse import urljoin,urlsplit

from bs4 import BeautifulSoup
from markdownify import markdownify

from backend.crawler.anexos import _cell


def normalize(text: str) -> str:
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c)).lower().split())


def parse_page(raw: bytes, info: dict) -> dict:
    soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser')
    heading=soup.find('h1')
    title=heading.get_text(' ',strip=True) if heading else ''
    body=(soup.select_one(info['content_selector']) if info.get('content_selector') else
          soup.select_one('#content-core .servico-content') or soup.select_one('#content-core') or soup.select_one('#page-document'))
    if not title or body is None or not body.get_text(' ',strip=True):
        raise ValueError('Página sem título ou conteúdo Gov.br reconhecível.')
    for node in body.select('script,style,nav,footer,form,.avaliacao-container,.canais-atendimento'):
        node.decompose()
    if not body.get_text(' ',strip=True):
        raise ValueError('Página sem conteúdo editorial após limpeza.')
    identity=normalize(title+' '+body.get_text(' ',strip=True))
    if not all(normalize(token) in identity for token in info['identity']):
        raise ValueError('Página não corresponde à identidade esperada.')
    for link in body.find_all('a',href=True):
        url=urljoin(info['url'],link['href'])
        if urlsplit(url).scheme in ('http','https','mailto'):link['href']=url
        else:del link['href']
    tables=[]
    for number,table in enumerate(list(body.find_all('table')),1):
        if table.find_parent('table') is not None:
            raise ValueError('Tabela aninhada exige revisão do parser.')
        rows=[]
        for row_number,row in enumerate(table.find_all('tr'),1):
            cells=[]
            for column,cell in enumerate(row.find_all(['td','th'],recursive=False),1):
                rowspan,colspan=int(cell.get('rowspan',1)),int(cell.get('colspan',1))
                if not (1<=rowspan<=10000 and 1<=colspan<=10000):raise ValueError('Mesclagem de células inválida.')
                cells.append({'posicao':column,'texto':cell.get_text(' ',strip=True),
                              'rowspan':rowspan,'colspan':colspan,'tag':cell.name})
            rows.append({'numero':row_number,'celulas':cells})
        tables.append({'numero':number,'linhas':rows})
        placeholder=soup.new_tag('p');placeholder.string=f'Tabela {number}: consultar o inventário de células abaixo.'
        table.replace_with(placeholder)
    text=markdownify(str(body),heading_style='ATX',bullets='-',strip=['img']).strip()
    for table in tables:
        text+=f'\n\n## Tabela {table["numero"]} — células originais\n\n| Linha | Célula | Texto | rowspan | colspan |\n|---|---|---|---|---|\n'
        for row in table['linhas']:
            for cell in row['celulas']:
                text+=f'| {row["numero"]} | {cell["posicao"]} | {_cell(cell["texto"])} | {cell["rowspan"]} | {cell["colspan"]} |\n'
    return {'titulo_pagina':title,'markdown':text,'tabelas':tables}


def ingest(source: str, info: dict, raw: bytes, output: Path) -> Path:
    digest=hashlib.sha256(raw).hexdigest()
    target=Path(output)/source/digest
    result=target/'pagina.md'
    if target.exists():
        try:
            meta=json.loads((target/'metadados.json').read_text(encoding='utf-8'))
            if (not isinstance(meta,dict) or meta.get('sha256')!=digest or meta.get('source_url')!=info['url']
                    or meta.get('source_id')!=source or (target/'original.html').read_bytes()!=raw
                    or not result.is_file() or not (target/'tabelas.json').is_file()):
                raise ValueError('Versão existente incompleta ou divergente.')
        except (OSError,ValueError) as exc:
            raise ValueError('Versão existente incompleta ou divergente.') from exc
        return result
    data=parse_page(raw,info)
    meta={'source_id':source,'titulo':info.get('title',data['titulo_pagina']),
        'titulo_pagina':data['titulo_pagina'],'source_url':info['url'],
        'camada':info.get('camada','B'),'tipo':info.get('kind','pagina_oficial'),
        'periodo_agenda':info.get('periodo'),'data_publicada_no_titulo':info.get('data_publicada'),
        'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),
        'tabelas':len(data['tabelas']),
        'linhas_tabelas':sum(len(t['linhas']) for t in data['tabelas']),
        'celulas':sum(len(r['celulas']) for t in data['tabelas'] for r in t['linhas']),
        'status':'extraido','vigencia':'nao_verificada','revisao_humana':'pendente'}
    text='\n'.join(['---',f'source_id: {source}',f'source_url: {info["url"]}',
        f'camada: {meta["camada"]}',f'sha256: {digest}',f'coletado_em: {meta["coletado_em"]}',
        'vigencia: nao_verificada','revisao_humana: pendente','---','',f'# {data["titulo_pagina"]}','',
        '[HTML original](original.html) · [Metadados](metadados.json) · [Tabelas literais](tabelas.json)','',
        '> Conteúdo oficial coletado para pesquisa. Prazos e condições exigem revisão da publicação e da aplicabilidade por empresa. Células são preservadas sem inferir alinhamento de colunas mescladas ou regras recorrentes.','',data['markdown'],''])
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.coleta-',dir=target.parent))
    try:
        (staging/'original.html').write_bytes(raw)
        (staging/'pagina.md').write_text(text,encoding='utf-8')
        (staging/'tabelas.json').write_text(json.dumps(data['tabelas'],ensure_ascii=False,indent=2),encoding='utf-8')
        (staging/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return result
