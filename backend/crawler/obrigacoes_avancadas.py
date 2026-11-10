"""Recorte oficial de DCTFWeb, eSocial e EFD-Reinf; não infere incidência por empresa."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import shutil
from urllib.parse import urlsplit
import zipfile

import httpx
from bs4 import BeautifulSoup
import pypdfium2 as pdfium
from backend.crawler import manuais, paginas, esquemas
from backend.crawler.anexos import _write_atomic

DEFAULT_OUTPUT = Path(__file__).resolve().parent/'data'/'obrigacoes-avancadas'
ES = 'https://www.gov.br/esocial/pt-br/documentacao-tecnica'
RE = 'https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/efd-reinf'
DC = 'https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/manuais/manual-dctfweb'
LIMITES = ('Recorte: catálogos e orientação, manuais operacionais, MOS e leiautes/XSD '
           'indicados abaixo; não inclui todo histórico, minutas ou pacotes com produção futura. '
           'A disponibilização não comprova vigência. Nenhuma obrigação é presumida para todo MEI. '
           'PDFs grandes: texto por página sem reconstrução de tabelas/imagens; revisão humana pendente. '
           'XSD: inventário estrutural, sem validação ou execução de eventos. Catálogos SPED são '
           'coletados pela API pública porque o HTML da listagem contém somente Carregando.')

def source(title, url, identity, kind='html', catalog=None, version='não declarada'):
    return dict(title=title,url=url,identity=identity,kind=kind,catalog_url=catalog or url,
                versao_documental=version,publicador='Receita Federal / eSocial / SPED')

def api(url):
    return url.replace('/sped/', '/sped/++api++/')

SOURCES = {
 'dctfweb-orientacoes': source('DCTFWeb orientação tributária','https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/declaracoes-e-demonstrativos/DCTFWeb/dctfweb-declaracao-de-debitos-e-creditos-tributarios-federais',['dctfweb']),
 'dctfweb-catalogo': source('Catálogo DCTFWeb',DC,['dctfweb']),
 'dctfweb-manual': source('Manual DCTFWeb janeiro/2025',DC+'/manual-dctfweb-atualizacao-janeiro2025_versao_final.pdf', ['dctfweb'],'pdf',DC,'janeiro/2025'),
 'esocial-documentacao': source('Documentação técnica eSocial',ES,['documentacao','esocial']),
 'esocial-web-mei': source('Manual eSocial Web MEI',ES+'/manuais/manual-do-usuario-esocial-web-mei-versao-de-06-02-2026.pdf',['esocial','mei'],'pdf',ES,'06/02/2026'),
 'esocial-web-geral': source('Manual eSocial Web Geral',ES+'/manuais/manual-do-usuario-esocial-web-geral.pdf',['esocial'],'pdf',ES),
 'esocial-mos': source('MOS eSocial S-1.3 NO12/2026',ES+'/manuais/mos-s-1-3-consolidada-ate-a-no-s-1-3-12-2026.pdf',['esocial'],'pdf',ES,'S-1.3 consolidado NO12/2026'),
 'esocial-leiautes': source('Leiautes eSocial NT07/2026 rev20/10/2026',ES+'/manuais/nota-tecnica-s-1-3-07-2026-rev-20-10-2026-pdf.zip',['esocial'],'pdf_zip',ES,'S-1.3 NT07/2026 rev20/10/2026'),
 'esocial-xsd': source('XSD eSocial produção26/10/2026',ES+'/manuais/2026-10-26_esquemas_xsd_v_s_01_03_00-1-1.zip',['esocial'],'xsd',ES,'S-1.3 NT07/2026 produção26/10/2026'),
 'esocial-nota-tecnica': source('Nota técnica eSocial07/2026 rev20/10',ES+'/manuais/nota-tecnica-s-1-3-07-2026-rev-20-10-2026.pdf',['esocial'],'pdf',ES,'NT07/2026 rev20/10/2026'),
 'reinf-orientacoes': source('EFD-Reinf orientação oficial',api(RE),['reinf'],'json',RE),
 'reinf-catalogo': source('Catálogo manuais Reinf',api(RE+'/manuais-e-documentos-tecnicos')+'?b_size=100',['manuais'],'json',RE),
 'reinf-leiautes-catalogo': source('Catálogo leiautes Reinf',api(RE+'/documento-tecnicos/versao-atual/leiautes')+'?b_size=100',['leiautes'],'json',RE),
 'reinf-xsd-catalogo': source('Catálogo XSD Reinf',api(RE+'/documento-tecnicos/versao-atual/esquemas-xsd')+'?b_size=100',['xsd'],'json',RE),
 'reinf-manual': source('Manual usuário Reinf2.1.2.1',RE+'/manuais-e-documentos-tecnicos/manual-da-efd-reinf-versao-2-1-2-1.pdf/@@display-file/file',['reinf'],'pdf',RE,'2.1.2.1'),
 'reinf-desenvolvedor': source('Manual desenvolvedor Reinf2.8',RE+'/manuais-e-documentos-tecnicos/manualorientacaodesenvolvedor-reinf-v2-8.pdf/@@download/file',['reinf'],'pdf',RE,'2.8'),
 'reinf-leiautes': source('Leiautes Reinf2.1.2b',RE+'/documento-tecnicos/versao-atual/leiautes/v-2-1.2b/versao-2-1-2b/@@download/file',['reinf'],'pdf_zip',RE,'2.1.2b até NT03/2025'),
 'reinf-xsd': source('XSD Reinf2.1.2 23/09/2026',RE+'/documento-tecnicos/versao-atual/esquemas-xsd/xsd-efd-reinf-v2-1-2-23092026.zip/@@download/file',['reinf'],'xsd',RE,'2.1.2 23/09/2026'),
}

def official(url):
    parts=urlsplit(url)
    return parts.scheme=='https' and parts.hostname=='www.gov.br'

def parse_json(raw, info):
    data=json.loads(raw)
    text=' '.join([data.get('title',''),data.get('description','')]+[
        block.get('plaintext','') for block in data.get('blocks',{}).values()])
    items=data.get('items',[])
    if not all(paginas.normalize(t) in paginas.normalize(text) for t in info['identity']):
        raise ValueError('Identidade da API divergente.')
    if not items and len(text)<150:
        raise ValueError('API sem conteúdo substantivo.')
    if data.get('items_total',len(items))>len(items):
        raise ValueError('Catálogo paginado incompleto; aumentar b_size.')
    lines=[text,'','## Itens do catálogo','']
    for item in items:
        url=item.get('@id','')
        if not official(url):raise ValueError('Link não oficial no catálogo.')
        lines.append(f'- [{item["title"]}]({url}) — {item.get("mime_type", "")}')
    return '\n'.join(lines),{'itens_catalogo':len(items)}

def pdf_text(raw):
    if not raw.startswith(b'%PDF-'):raise ValueError('Resposta não é PDF.')
    try:
        with pdfium.PdfDocument(raw) as document:
            pages=[]
            for page in document:
                textpage=page.get_textpage()
                try:pages.append(textpage.get_text_range())
                finally:
                    textpage.close()
                    page.close()
            return pages
    except pdfium.PdfiumError as exc:
        raise ValueError('PDF inválido.') from exc

def pdf_members(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members=archive.infolist()
            if len(members)>200 or sum(m.file_size for m in members)>100*1024*1024:
                raise ValueError('ZIP de PDFs excede limites.')
            result=[]
            for member in members:
                path=member.filename.replace('\\','/')
                if path.startswith('/') or '..' in Path(path).parts or ':' in path:
                    raise ValueError('Caminho inseguro no ZIP.')
                if path.lower().endswith('.pdf'):
                    result.append((path,archive.read(member)))
            if not result:raise ValueError('ZIP sem PDFs.')
            return result
    except zipfile.BadZipFile as exc:
        raise ValueError('Resposta não é ZIP válido.') from exc

def ingest(source_id, info, raw, output):
    if not official(info['url']):raise ValueError('Fonte não oficial.')
    digest=hashlib.sha256(raw).hexdigest()
    target=Path(output)/source_id/digest
    if target.exists():
        meta=json.loads((target/'metadados.json').read_text(encoding='utf-8'))
        original=target/meta['original']
        if original.read_bytes()!=raw or meta['sha256']!=digest or meta['source_url']!=info['url'] or not (target/meta['markdown_file']).is_file():
            raise ValueError('Versão existente incompleta ou divergente.')
        return target/meta['markdown_file']
    kind=info['kind'];extra={};children=[]
    if kind=='xsd':
        docs=esquemas.parse_package(raw)
        namespace=next((d['target_namespace'] for d in docs if all(t in d['target_namespace'].lower() for t in info['identity'])),None)
        if not namespace:raise ValueError('Pacote XSD não corresponde à família.')
        result=esquemas.ingest(source_id,{**info,'identity_namespace':namespace},raw,output)
        meta=json.loads((result.parent/'metadados.json').read_text(encoding='utf-8'))
        meta.update(original='original.zip',markdown_file=result.name,versao_documental=info['versao_documental'])
        _write_atomic(result.parent/'metadados.json',json.dumps(meta,ensure_ascii=False,indent=2))
        return result
    if kind=='html':
        # eSocial atual usa #content; o adaptador preserva o original recebido.
        soup=BeautifulSoup(raw.decode('utf-8-sig'),'html.parser')
        if soup.select_one('#content-core, #page-document'):
            result=paginas.ingest(source_id,info,raw,output)
            meta=json.loads((result.parent/'metadados.json').read_text(encoding='utf-8'))
            meta.update(original='original.html',markdown_file=result.name,versao_documental=info['versao_documental'])
            _write_atomic(result.parent/'metadados.json',json.dumps(meta,ensure_ascii=False,indent=2))
            return result
        body=soup.select_one('#content')
        if not body or len(body.get_text(' ',strip=True))<200:raise ValueError('HTML shell sem conteúdo.')
        body['id']='content-core'
        parsed=paginas.parse_page(str(soup).encode(),info)
        text=parsed['markdown'];extra={'tabelas':len(parsed['tabelas']),'adaptador':'Gov.br #content para parser paginas'};ext='html'
    elif kind=='json':text,extra=parse_json(raw,info);ext='json'
    elif kind in ('pdf','pdf_zip'):
        members=pdf_members(raw) if kind=='pdf_zip' else [('documento.pdf',raw)]
        texts=[];total=0;missing=[]
        for name,content in members:
            pages=pdf_text(content)
            identity=paginas.normalize(' '.join(pages[:3]))
            if not all(paginas.normalize(t) in identity for t in info['identity']):
                raise ValueError(f'PDF não corresponde à identidade: {name}.')
            if kind=='pdf' and len(pages)<=25:
                result=manuais.ingest(source_id,raw,output,source_info=info)
                meta=json.loads((result.parent/'metadados.json').read_text(encoding='utf-8'))
                meta.update(original='original.pdf',markdown_file=result.name,versao_documental=info['versao_documental'])
                _write_atomic(result.parent/'metadados.json',json.dumps(meta,ensure_ascii=False,indent=2))
                return result
            total+=len(pages)
            texts.extend([f'# Arquivo: {name}',''])
            for n,text_page in enumerate(pages,1):
                texts.extend([f'## Página {n}','',text_page,''])
                if not text_page.strip():missing.append({'arquivo':name,'pagina':n})
            children.append({'arquivo':name,'sha256':hashlib.sha256(content).hexdigest(),'paginas':len(pages)})
        text='\n'.join(texts);ext='zip' if kind=='pdf_zip' else 'pdf'
        extra={'paginas':total,'arquivos_pdf':len(members),'membros':children,'paginas_sem_texto':missing,
               'extrator':'pypdfium2','versao_extrator':str(pdfium.PYPDFIUM_INFO),
               'limite_extracao':'Texto apenas; tabelas e imagens não reconstruídas.'}
    else:raise ValueError('Tipo desconhecido.')
    meta=dict(source_id=source_id,titulo=info['title'],source_url=info['url'],catalog_url=info['catalog_url'],
              sha256=digest,coletado_em=datetime.now(timezone.utc).isoformat(),status='ocr_pendente' if extra.get('paginas_sem_texto') else 'extraido',
              revisao_humana='pendente',vigencia='nao_verificada',camada='B',tipo=kind,
              versao_documental=info['versao_documental'],original='original.'+ext,markdown_file='documento.md',**extra)
    header=['---']+[f'{k}: {meta[k]}' for k in ['source_id','source_url','sha256','coletado_em','status','revisao_humana','vigencia']]+['---','',f'# {info["title"]}','',LIMITES,'',text]
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.coleta-',dir=target.parent))
    try:
        (staging/meta['original']).write_bytes(raw)
        (staging/'documento.md').write_text('\n'.join(header),encoding='utf-8',newline='\n')
        (staging/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return target/'documento.md'

def collect(sources,output,client):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);results=[]
    for key in sources:
        info=SOURCES[key]
        try:
            response=client.get(info['url']);response.raise_for_status()
            if not official(str(response.url)):raise ValueError('Redirecionamento não oficial.')
            path=ingest(key,info,response.content,output)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError,KeyError) as exc:
            results.append(dict(source_id=key,titulo=info['title'],source_url=info['url'],status='erro',erro=str(exc)))
        print(key+': '+results[-1]['status'],flush=True)
    report=dict(executado_em=datetime.now(timezone.utc).isoformat(),limites=LIMITES,total=len(results),
                pendencias=sum(r['status'] not in ('extraido','erro') for r in results),
                sucesso=sum(r['status']=='extraido' for r in results),erros=sum(r['status']=='erro' for r in results),documentos=results)
    lines=['# Obrigações avançadas — recorte oficial','',LIMITES,'','| Fonte | Versão documental | Estado | Páginas | XSD |','|---|---|---|---|---|']
    for r in results:
        link=f'[{r["titulo"]}]({r["markdown"]})' if 'markdown' in r else r['titulo']
        lines.append(f'| {link} | {r.get("versao_documental", "")} | {r["status"]} | {r.get("paginas", "")} | {r.get("arquivos_xsd", "")} |')
        if 'erro' in r:lines.append(f'\nFalha {r["source_id"]}: {r["erro"]}\n')
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=['all',*SOURCES],default='all')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    with httpx.Client(timeout=120,follow_redirects=True,headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client:
        report=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client)
    print(json.dumps({k:v for k,v in report.items() if k!='documentos'},ensure_ascii=False))
    return int(report['erros']>0 or report['pendencias']>0)

if __name__=='__main__':raise SystemExit(main())
