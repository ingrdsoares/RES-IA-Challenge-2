"""Inventário de declarações XSD em pacotes ZIP oficiais, sem compilar schemas."""

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import tempfile
from urllib.parse import urlsplit
import zipfile

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from backend.crawler.anexos import _cell

XS = '{http://www.w3.org/2001/XMLSchema}'
MAX_ENTRIES = 2000
MAX_TOTAL = 50 * 1024 * 1024
MAX_XSD = 10 * 1024 * 1024



def _without_doctype(content: bytes) -> tuple[bytes, bool]:
    # Ignorar a declaração sem carregar DTD nem expandir entidades; o original permanece no ZIP.
    start=content.find(b'<!DOCTYPE')
    if start<0:
        return content,False
    quote=None
    subset=0
    position=start+9
    while position<len(content):
        char=content[position]
        if quote is not None:
            if char==quote:quote=None
        elif content[position:position+4]==b'<!--':
            end=content.find(b'-->',position+4)
            if end<0:raise ValueError('Comentário DTD incompleto.')
            position=end+3
            continue
        elif char in (34,39):quote=char
        elif char==91:subset+=1
        elif char==93:subset-=1
        elif char==62 and subset==0:
            return content[:start]+content[position+1:],True
        position+=1
    raise ValueError('Declaração DTD incompleta.')


def parse_package(raw: bytes) -> list[dict]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ValueError('Resposta não é um ZIP válido.') from exc
    with archive:
        members=archive.infolist()
        if len(members)>MAX_ENTRIES or sum(m.file_size for m in members)>MAX_TOTAL:
            raise ValueError('Pacote excede os limites de entradas/tamanho descompactado.')
        names={}
        for member in members:
            name=member.filename.replace('\\','/')
            if name.startswith('/') or re.match(r'^[a-zA-Z]:',name) or '..' in PurePosixPath(name).parts:
                raise ValueError('Caminho inseguro no pacote ZIP.')
            if name in names:
                raise ValueError('Entrada duplicada no ZIP.')
            names[name]=member
        files=sorted(name for name,m in names.items() if not m.is_dir() and name.lower().endswith('.xsd'))
        if not files:
            raise ValueError('ZIP sem arquivos XSD.')
        docs=[]
        for name in files:
            if names[name].file_size>MAX_XSD:
                raise ValueError('XSD excede o limite individual.')
            try:
                content=archive.read(names[name])
                safe_content,ignored_dtd=_without_doctype(content)
                root=ET.fromstring(safe_content,forbid_dtd=True,forbid_entities=True,forbid_external=True)
            except (ET.ParseError,DefusedXmlException,zipfile.BadZipFile,RuntimeError) as exc:
                raise ValueError(f'XML inválido ou inseguro: {name}.') from exc
            if root.tag!=XS+'schema':
                raise ValueError(f'Arquivo não é XML Schema: {name}.')
            declarations=[]
            def walk(node,path,depth=0):
                if depth>200:
                    raise ValueError('Profundidade XML excede o limite.')
                if node.tag.startswith(XS):
                    kind=node.tag[len(XS):]
                    if kind not in ('schema','annotation','documentation','appinfo','include','import'):
                        description=' '.join(' '.join(d.itertext()) for d in node.findall(XS+'annotation/'+XS+'documentation'))
                        declarations.append({'categoria':kind,'caminho_xsd':path,**node.attrib,
                                             'documentacao':' '.join(description.split())})
                counters={}
                for child in node:
                    if not isinstance(child.tag,str) or not child.tag.startswith(XS):
                        continue
                    tag=child.tag[len(XS):]
                    counters[tag]=counters.get(tag,0)+1
                    walk(child,f'{path}/xs:{tag}[{counters[tag]}]',depth+1)
            walk(root,'/xs:schema')
            dependencies=[]
            for kind in ('include','import','redefine'):
                for node in root.findall(XS+kind):
                    location=node.get('schemaLocation','')
                    external=bool(urlsplit(location).scheme or location.startswith('//'))
                    resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),location)) if location and not external else ''
                    dependencies.append({'tipo':kind,'schemaLocation':location,'namespace':node.get('namespace',''),
                        'arquivo_resolvido':resolved,'externa':external,
                        'presente_no_pacote':resolved in files if resolved else False})
            docs.append({'arquivo':name,'sha256':hashlib.sha256(content).hexdigest(),
                'target_namespace':root.get('targetNamespace',''), 'atributos_schema':root.attrib, 'dtd_ignorada':ignored_dtd,
                'declaracoes':declarations,'dependencias':dependencies})
        return docs


def ingest(source: str, info: dict, raw: bytes, output: Path) -> Path:
    digest=hashlib.sha256(raw).hexdigest()
    parent=Path(output)/source
    target=parent/digest
    result=target/'esquemas.md'
    if target.exists():
        if (target/'original.zip').read_bytes()!=raw or not result.is_file() or not (target/'catalogo.json').is_file() or not (target/'metadados.json').is_file():
            raise ValueError('Versão existente incompleta ou divergente.')
        return result
    docs=parse_package(raw)
    if not any(d['target_namespace']==info['identity_namespace'] for d in docs):
        raise ValueError('Namespace esperado ausente; pacote não corresponde à fonte.')
    missing=[{'arquivo':d['arquivo'],**dep} for d in docs for dep in d['dependencias'] if not dep['presente_no_pacote']]
    meta={'source_id':source,'titulo':info['title'],'source_url':info['url'],
        'catalog_url':info['catalog_url'],'camada':'A','tipo':'esquemas_xsd',
        'sha256':digest,'coletado_em':datetime.now(timezone.utc).isoformat(),
        'arquivos_xsd':len(docs),'declaracoes':sum(len(d['declaracoes']) for d in docs),
        'elementos':sum(x['categoria']=='element' for d in docs for x in d['declaracoes']),
        'dependencias_ausentes':missing,'status':'dependencias_pendentes' if missing else 'extraido',
        'vigencia':'nao_verificada','revisao_humana':'pendente'}
    lines=['---',f'source_id: {source}',f'source_url: {info["url"]}',f'catalog_url: {info["catalog_url"]}',
        'camada: A',f'sha256: {digest}',f'coletado_em: {meta["coletado_em"]}',f'arquivos_xsd: {len(docs)}',
        f'status: {meta["status"]}','vigencia: nao_verificada','revisao_humana: pendente','---','',
        f'# {info["title"]}','','[ZIP original](original.zip) · [Catálogo estruturado](catalogo.json) · [Metadados](metadados.json)','',
        '> Inventário de declarações XSD, sem compilação ou validação de XMLs de notas. Caminhos identificam a árvore do schema, não instâncias XML. Ocorrências e tipos são atributos declarados; escolhas e grupos podem alterar a obrigatoriedade final. Includes/imports externos não são baixados.','']
    columns=['categoria','caminho_xsd','name','ref','type','base','minOccurs','maxOccurs','use','value','documentacao']
    for doc in docs:
        lines.extend([f'## {_cell(doc["arquivo"])}','',f'Namespace: `{doc["target_namespace"]}`',f'SHA-256 do XSD: `{doc["sha256"]}`','','### Dependências',''])
        if doc['dtd_ignorada']:
            lines.extend(['> DTD ignorada na leitura. Sem expansão de entidades ou atributos padrão de DTD. Consultar o ZIP original.', ''])
        for dep in doc['dependencias']:
            state='presente' if dep['presente_no_pacote'] else 'PENDENTE'
            lines.append(f'- {dep["tipo"]}: `{dep["schemaLocation"]}` — {state}')
        if not doc['dependencias']:
            lines.append('Nenhuma dependência declarada.')
        lines.extend(['','### Declarações','','| '+' | '.join(columns)+' |','| '+' | '.join('---' for _ in columns)+' |'])
        for entry in doc['declaracoes']:
            lines.append('| '+' | '.join(_cell(entry.get(col,'')) for col in columns)+' |')
        lines.append('')
    parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.coleta-',dir=parent))
    try:
        (staging/'original.zip').write_bytes(raw)
        (staging/'esquemas.md').write_text('\n'.join(lines),encoding='utf-8')
        (staging/'catalogo.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2),encoding='utf-8')
        (staging/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return result
