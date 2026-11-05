"""Coleta manuais e perguntas e respostas oficiais do Simples Nacional/MEI."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata

import httpx
import pdfplumber

from backend.crawler.anexos import extract_pdf, _cell, _write_atomic

CATALOG_URL = 'https://www8.receita.fazenda.gov.br/SimplesNacional/ConteudoApoio/Manuais/TelaManuais.aspx'
PDF_BASE = 'https://www8.receita.fazenda.gov.br/SimplesNacional/Arquivos/manual/'
SOURCES = {
    'pgdas-defis': {'title': 'Manual do PGDAS-D e DEFIS', 'url': PDF_BASE+'MANUAL_PGDAS-D_2018_V4.pdf', 'identity': ['pgdas', 'defis'], 'kind': 'manual'},
    'pgmei': {'title': 'Manual do PGMEI', 'url': PDF_BASE+'MANUAL_PGMEI_2018.pdf', 'identity': ['pgmei'], 'kind': 'manual'},
    'dasn-simei': {'title': 'Manual da DASN-SIMEI', 'url': PDF_BASE+'Manual_DASN-SIMEI.pdf', 'identity': ['dasn', 'simei'], 'kind': 'manual'},
    'perguntas-simples': {'title': 'Perguntas e respostas — Simples Nacional', 'url': PDF_BASE+'PerguntaoSN.pdf', 'identity': ['perguntas', 'simples nacional'], 'kind': 'perguntas_respostas'},
    'perguntas-mei': {'title': 'Perguntas e respostas — MEI', 'url': PDF_BASE+'PerguntaoMEI.pdf', 'identity': ['perguntas', 'mei'], 'kind': 'perguntas_respostas'},
}
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'manuais'


def ingest(source: str, raw: bytes, output: Path, *, source_info: dict | None = None) -> Path:
    info = source_info if source_info is not None else SOURCES[source]
    digest = hashlib.sha256(raw).hexdigest()
    parent = Path(output)/source
    target = parent/digest
    result = target/'documento.md'
    if target.exists():
        meta=json.loads((target/'metadados.json').read_text(encoding='utf-8'))
        if ((target/'original.pdf').read_bytes()!=raw or not result.is_file()
                or meta['sha256']!=digest or meta['source_url']!=info['url']):
            raise ValueError('Versão existente incompleta ou divergente.')
        return result
    pages=extract_pdf(raw)
    initial=' '.join(page['texto'] for page in pages[:3])
    normalized=''.join(c for c in unicodedata.normalize('NFKD',initial) if not unicodedata.combining(c)).lower()
    normalized=re.sub(r'[^a-z0-9]+',' ',normalized)
    if not all(token.lower() in normalized for token in info['identity']):
        raise ValueError(f'PDF não corresponde à identidade esperada: {info["title"]}.')
    missing=[page['pagina'] for page in pages if not page['texto'].strip()]
    meta={'source_id': source, 'titulo': info['title'], 'tipo': info['kind'],
        'source_url': info['url'], 'catalog_url': info.get('catalog_url', CATALOG_URL), 'camada': info.get('camada', 'B'),
        'publicador': info.get('publicador', 'Receita Federal / Simples Nacional'),
        'sha256': digest, 'coletado_em': datetime.now(timezone.utc).isoformat(),
        'paginas': len(pages), 'tabelas': sum(len(page['tabelas']) for page in pages),
        'paginas_sem_texto': missing, 'status': 'ocr_pendente' if missing else 'extraido',
        'vigencia': 'nao_verificada', 'revisao_humana': 'pendente',
        'extrator': 'pdfplumber', 'versao_extrator': pdfplumber.__version__}
    lines=['---',f'source_id: {source}', f'source_url: {info["url"]}',
        f'catalog_url: {meta["catalog_url"]}', f'camada: {meta["camada"]}', f'tipo: {info["kind"]}',
        f'sha256: {digest}', f'coletado_em: {meta["coletado_em"]}',
        f'paginas: {meta["paginas"]}',f'tabelas: {meta["tabelas"]}',f'status: {meta["status"]}',
        'vigencia: nao_verificada','revisao_humana: pendente','---','',f'# {info["title"]}','',
        '[PDF original](original.pdf) · [Metadados](metadados.json)','',
        f'> Documento oficial, camada {meta["camada"]}. A data de coleta não comprova atualização ou vigência das regras. Extração automática; imagens e telas permanecem no PDF original, sem transcrição automática. Tabelas e exemplos exigem revisão antes do uso fiscal.','']
    for page in pages:
        lines.extend([f'## Página {page["pagina"]}', '', '### Texto extraído',''])
        if page['texto'].strip():
            fence='```'
            while fence in page['texto']:
                fence+='`'
            lines.extend([fence+'text',page['texto'],fence,''])
        else:
            lines.extend(['> OCR PENDENTE: página sem texto extraível. Consultar o PDF original.',''])
        for number,table in enumerate(page['tabelas'],1):
            if not table:
                continue
            columns=max(len(row) for row in table)
            lines.extend([f'### Tabela {number}', '',
                '| '+' | '.join(f'Coluna {i}' for i in range(1,columns+1))+' |',
                '| '+' | '.join('---' for _ in range(columns))+' |'])
            for row in table:
                cells=list(row)+['']*(columns-len(row))
                lines.append('| '+' | '.join(_cell(cell) for cell in cells)+' |')
            lines.append('')
    parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.coleta-',dir=parent))
    try:
        (staging/'original.pdf').write_bytes(raw)
        (staging/'documento.md').write_text('\n'.join(lines),encoding='utf-8')
        (staging/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return result


def collect(sources: list[str], output: Path, client: httpx.Client) -> dict:
    results=[]
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    for source in sources:
        info=SOURCES[source]
        try:
            response=client.get(info['url'])
            response.raise_for_status()
            path=ingest(source,response.content,output)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc:
            results.append({'source_id':source,'titulo':info['title'],'source_url':info['url'],
                            'status':'erro','erro':str(exc)})
        print(f'{source}: {results[-1]["status"]}',flush=True)
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'documentos':results}
    lines=['# Manuais e perguntas e respostas — Simples Nacional e MEI','',
        f'[Catálogo oficial]({CATALOG_URL})','',
        '> Documentos de orientação oficial (camada B). Revisão de vigência e qualidade da extração pendente. Este índice reflete a última execução; versões anteriores permanecem no disco.','',
        '| Documento | Estado | Páginas | Tabelas detectadas |','|---|---|---|---|']
    for item in results:
        title=_cell(item['titulo'])
        link=f'[{title}]({item["markdown"]})' if 'markdown' in item else title
        lines.append(f'| {link} | {item["status"]} | {item.get("paginas", "")} | {item.get("tabelas", "")} |')
    for item in results:
        if 'erro' in item:
            lines.extend(['',f'> Falha em {item["source_id"]}: {_cell(item["erro"])}'])
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=[*SOURCES,'all'],default='all')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    try:
        with httpx.Client(timeout=90,follow_redirects=True,
                          headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client:
            report=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client)
        pending=sum(item['status']!='extraido' for item in report['documentos'])
        print(f'Documentos: {report["total"]}; pendências/erros: {pending}')
        print(f'Índice: {(args.output/"indice.md").resolve()}')
        return int(pending>0)
    except (ValueError,OSError) as exc:
        print(f'Falha na coleta de manuais: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
