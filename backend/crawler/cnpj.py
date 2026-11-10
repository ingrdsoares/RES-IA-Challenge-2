"""Recorte inicial de Empresas e tabelas auxiliares dos dados abertos CNPJ."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit
import zipfile

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
import httpx

from backend.crawler.anexos import _cell, _write_atomic
from backend.crawler.manuais import ingest as ingest_pdf

SHARE='https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9'
DAV='https://arquivos.receitafederal.gov.br/public.php/webdav/'
PUBLIC_AUTH=('YggdBLfdninEJX9','')  # Identificador do compartilhamento público, sem senha.
LAYOUT_URL='https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf'
AUXILIARY={'cnaes':'Cnaes.zip','naturezas':'Naturezas.zip','qualificacoes':'Qualificacoes.zip',
           'municipios':'Municipios.zip','paises':'Paises.zip','motivos':'Motivos.zip'}
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'cnpj'
MAX_DOWNLOAD=120*1024*1024
EMPRESA_FIELDS=['cnpj_basico','razao_social','natureza_juridica','qualificacao_responsavel',
                'capital_social_declarado','porte','ente_federativo_responsavel']


def _competence(value: str) -> str:
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',value):
        raise ValueError('Competência deve ser AAAA-MM.')
    return value


def latest_competence(raw: bytes) -> str:
    try:
        root=ET.fromstring(raw,forbid_dtd=True,forbid_entities=True,forbid_external=True)
    except (ET.ParseError,DefusedXmlException) as exc:
        raise ValueError('Listagem mensal não contém XML WebDAV válido.') from exc
    months=[]
    for response in root.findall('{DAV:}response'):
        href=response.findtext('{DAV:}href','')
        name=unquote(urlsplit(href).path).rstrip('/').split('/')[-1]
        if re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',name):months.append(name)
    if not months:raise ValueError('Nenhuma competência publicada encontrada.')
    return max(months)


def _member(archive: zipfile.ZipFile, max_size: int):
    members=[m for m in archive.infolist() if not m.is_dir()]
    if len(members)!=1:raise ValueError('Esperado exatamente um arquivo CSV por ZIP.')
    member=members[0]
    name=member.filename.replace('\\','/')
    if name.startswith('/') or '..' in PurePosixPath(name).parts or re.match(r'^[A-Za-z]:',name):
        raise ValueError('Caminho inválido no ZIP.')
    if member.file_size>max_size:raise ValueError('Conteúdo descompactado excede o limite.')
    return member


def parse_empresas(path: Path, *, limit: int=100) -> tuple[list[dict],int]:
    if not 1<=limit<=10000:raise ValueError('Limite deve estar entre 1 e 10.000.')
    records,seen,scanned=[],set(),0
    try:
        with zipfile.ZipFile(path) as archive:
            member=_member(archive,500*1024*1024)
            with archive.open(member) as binary:
                reader=csv.reader(io.TextIOWrapper(binary,encoding='latin-1',newline=''),delimiter=';',strict=True)
                for row in reader:
                    scanned+=1
                    if len(row)!=7:raise ValueError(f'Linha {scanned}: esperado leiaute Empresas com sete colunas.')
                    if not re.fullmatch(r'[0-9A-Z]{8}',row[0]) or not row[1].strip():
                        raise ValueError(f'Linha {scanned}: código básico ou razão social inválidos.')
                    if row[0] in seen:raise ValueError('CNPJ básico duplicado no trecho lido.')
                    seen.add(row[0])
                    if row[5] not in ('01','03'):continue
                    records.append(dict(zip(EMPRESA_FIELDS,row)))
                    if len(records)==limit:break
    except (zipfile.BadZipFile,csv.Error,UnicodeError) as exc:
        raise ValueError('ZIP/CSV de Empresas inválido.') from exc
    if not records:raise ValueError('Nenhuma empresa de porte 01/03 encontrada no lote.')
    return records,scanned


def parse_auxiliary(raw: bytes) -> list[dict]:
    records,seen=[],set()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            member=_member(archive,5*1024*1024)
            with archive.open(member) as binary:
                reader=csv.reader(io.TextIOWrapper(binary,encoding='latin-1',newline=''),delimiter=';',strict=True)
                for row in reader:
                    if len(row)!=2 or not row[0].strip() or not row[1].strip():
                        raise ValueError('Tabela auxiliar deve conter código e descrição.')
                    if row[0] in seen:raise ValueError('Código auxiliar duplicado.')
                    seen.add(row[0]);records.append({'codigo':row[0],'descricao':row[1]})
    except (zipfile.BadZipFile,csv.Error,UnicodeError) as exc:
        raise ValueError('ZIP/CSV auxiliar inválido.') from exc
    if not records:raise ValueError('Tabela auxiliar vazia.')
    return records


def _url(competence: str, name: str) -> str:
    return DAV+_competence(competence)+'/'+quote(name)


def _publish(target: Path, original: Path | bytes, records: list[dict], meta: dict, notice: str) -> Path:
    result=target/'dados.md'
    if target.exists():
        existing=json.loads((target/'metadados.json').read_text(encoding='utf-8'))
        with (target/'original.zip').open('rb') as file:
            digest=hashlib.file_digest(file,'sha256').hexdigest()
        if existing['sha256']!=meta['sha256'] or digest!=meta['sha256'] or not result.is_file() or not (target/'registros.json').is_file():
            raise ValueError('Versão existente incompleta ou divergente.')
        return result
    lines=['---',f'source_id: {meta["source_id"]}',f'source_url: {meta["source_url"]}',
        f'competencia: {meta["competencia"]}',f'coletado_em: {meta["coletado_em"]}',
        f'sha256: {meta["sha256"]}',f'registros: {len(records)}','camada: A',
        'revisao_humana: pendente','---','',f'# {meta["titulo"]}','',
        '[ZIP original](original.zip) · [Registros](registros.json) · [Metadados](metadados.json)','',notice,'']
    columns=list(records[0])
    lines.extend(['| '+' | '.join(columns)+' |','| '+' | '.join('---' for _ in columns)+' |'])
    for record in records:lines.append('| '+' | '.join(_cell(record[field]) for field in columns)+' |')
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.coleta-',dir=target.parent))
    try:
        if isinstance(original,Path):shutil.copyfile(original,staging/'original.zip')
        else:(staging/'original.zip').write_bytes(original)
        (staging/'dados.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        (staging/'registros.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        (staging/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return result


def ingest_empresas(path: Path, output: Path, *, competence: str, limit: int=100) -> Path:
    _competence(competence)
    records,scanned=parse_empresas(path,limit=limit)
    with path.open('rb') as file:digest=hashlib.file_digest(file,'sha256').hexdigest()
    meta={'source_id':'empresas-amostra','titulo':'CNPJ — amostra de Empresas, portes 01/03',
        'source_url':_url(competence,'Empresas1.zip'),'compartilhamento_publico':SHARE,
        'competencia':competence,'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),
        'camada':'A','registros':len(records),'linhas_lidas':scanned,'limite_solicitado':limit,
        'lote':'Empresas1.zip','portes':['01','03'],'filtro_uf':None,
        'criterio':'primeiras correspondências na ordem do lote, sem representatividade estatística',
        'arquivo_original_bytes':path.stat().st_size,'validacao':'somente trecho necessário ao recorte',
        'status':'extraido','revisao_humana':'pendente'}
    target=Path(output)/competence/'empresas-amostra'/f'{digest}-n{limit}'
    notice='> Recorte técnico, não representativo: primeiras empresas de porte 01/03 encontradas somente em Empresas1.zip. CNPJ básico tem oito caracteres e não identifica um estabelecimento completo. Este arquivo não informa UF, CNAE, situação cadastral ou opção MEI/Simples. Capital social é o valor declarado, não faturamento.'
    return _publish(target,path,records,meta,notice)


def ingest_auxiliary(source: str, raw: bytes, output: Path, *, competence: str) -> Path:
    _competence(competence)
    records=parse_auxiliary(raw)
    digest=hashlib.sha256(raw).hexdigest()
    meta={'source_id':source,'titulo':f'CNPJ — tabela auxiliar {source}',
        'source_url':_url(competence,AUXILIARY[source]),'compartilhamento_publico':SHARE,
        'competencia':competence,'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),
        'camada':'A','registros':len(records),'status':'extraido','revisao_humana':'pendente'}
    return _publish(Path(output)/competence/source/digest,raw,records,meta,
        '> Tabela auxiliar oficial do CNPJ. Códigos preservados como texto. Códigos de município da Receita não devem ser tratados automaticamente como códigos IBGE.')


def download(client: httpx.Client, url: str, target: Path, *, max_bytes: int=MAX_DOWNLOAD) -> None:
    try:
        with client.stream('GET',url,auth=PUBLIC_AUTH) as response:
            response.raise_for_status()
            if int(response.headers.get('content-length','0'))>max_bytes:
                raise ValueError('Arquivo excede o limite de download.')
            size=0
            with target.open('wb') as file:
                for block in response.iter_bytes(1024*1024):
                    size+=len(block)
                    if size>max_bytes:raise ValueError('Arquivo excede o limite de download.')
                    file.write(block)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def collect(output: Path, client: httpx.Client, *, competence: str | None=None, limit: int=100, empresas_input: Path | None=None) -> dict:
    if not 1<=limit<=10000:raise ValueError('Limite deve estar entre 1 e 10.000.')
    if competence is None:
        body=b'<d:propfind xmlns:d="DAV:"><d:prop><d:displayname/><d:resourcetype/></d:prop></d:propfind>'
        response=client.request('PROPFIND',DAV,auth=PUBLIC_AUTH,headers={'Depth':'1'},content=body)
        response.raise_for_status();competence=latest_competence(response.content)
    _competence(competence)
    root=Path(output)/competence;root.mkdir(parents=True,exist_ok=True)
    results=[]
    with tempfile.TemporaryDirectory(prefix='.downloads-',dir=root,ignore_cleanup_errors=True) as temp:
        for source,name in [*AUXILIARY.items(),('empresas-amostra','Empresas1.zip'),('leiaute','cnpj-metadados.pdf')]:
            try:
                if source=='leiaute':
                    response=client.get(LAYOUT_URL,follow_redirects=True);response.raise_for_status()
                    info={'title':'CNPJ — leiaute oficial dos dados abertos','url':LAYOUT_URL,
                        'catalog_url':SHARE,'identity':['dados abertos','cnpj'],'kind':'leiaute',
                        'camada':'A','publicador':'Receita Federal'}
                    path=ingest_pdf('leiaute',response.content,root,source_info=info)
                elif source=='empresas-amostra':
                    file=empresas_input or Path(temp)/name
                    if empresas_input is None:download(client,_url(competence,name),file)
                    path=ingest_empresas(file,output,competence=competence,limit=limit)
                else:
                    file=Path(temp)/name
                    download(client,_url(competence,name),file,max_bytes=5*1024*1024)
                    path=ingest_auxiliary(source,file.read_bytes(),output,competence=competence)
                meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
                results.append({**meta,'markdown':path.relative_to(root).as_posix()})
            except (httpx.HTTPError,ValueError,OSError) as exc:
                results.append({'source_id':source,'titulo':source,'status':'erro','erro':str(exc)})
            print(f'{source}: {results[-1]["status"]}',flush=True)
    report={'competencia':competence,'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'fontes':results}
    lines=[f'# Dados abertos CNPJ — {competence}','','> Recorte inicial: leiaute, tabelas auxiliares e amostra técnica do lote Empresas1. Não é a base nacional completa. Índice da última execução.','',
        '| Fonte | Estado | Registros |','|---|---|---|']
    for item in results:
        title=_cell(item['titulo']);link=f'[{title}]({item["markdown"]})' if 'markdown' in item else title
        lines.append(f'| {link} | {item["status"]} | {item.get("registros", "")} |')
    for item in results:
        if 'erro' in item:lines.extend(['',f'> Falha em {item["source_id"]}: {_cell(item["erro"])}'])
    _write_atomic(root/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(root/'indice.md','\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--competencia',help='AAAA-MM; padrão: última pasta mensal publicada.')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--empresas-input',type=Path,help='Empresas1.zip local da competência informada.')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    if args.empresas_input and not args.competencia:parser.error('--empresas-input exige --competencia.')
    try:
        with httpx.Client(timeout=90,headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client:
            report=collect(args.output,client,competence=args.competencia,limit=args.limit,empresas_input=args.empresas_input)
        pending=sum(item['status']!='extraido' for item in report['fontes'])
        print(f'Competência: {report["competencia"]}; fontes: {report["total"]}; pendências/erros: {pending}')
        print(f'Índice: {(args.output/report["competencia"]/"indice.md").resolve()}')
        return int(pending>0)
    except (httpx.HTTPError,ValueError,OSError) as exc:
        print(f'Falha na coleta CNPJ: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
