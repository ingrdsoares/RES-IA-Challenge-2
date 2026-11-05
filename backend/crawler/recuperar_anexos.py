"""Recuperação local de anexos Word/OCR, sem alterar originais nem suas versões."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
from bs4 import BeautifulSoup
from .cnpj_df import digest
from .legislacao import _convert

DATA=Path(__file__).resolve().parent/'data'
DEFAULT_OUTPUT=DATA/'anexos-recuperados'
POWERSHELL=Path('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')


def render(raw,kind,url):
    text=raw.decode('utf-8-sig')
    if kind=='word':
        soup=BeautifulSoup(text,'html.parser')
        for node in soup.select('script,style'):node.decompose()
        body=_convert(str(soup.body or soup),url)
        stats={'tabelas':len(soup.find_all('table')),'extrator':'Microsoft Word HTML filtrado'}
    else:
        body='> OCR automático pt-BR; erros de reconhecimento e de ordem das células podem ocorrer. Revisão humana pendente.\n\n'+text
        stats={'extrator':'Windows.Media.Ocr','idioma':'pt-BR'}
    if len(text.strip())<10 or not body.strip():raise ValueError('Extração vazia/insuficiente')
    return body,stats


def verify(target,meta):
    for name,checksum in meta['artefatos_sha256'].items():
        if digest(Path(target)/name)!=checksum:raise ValueError('Derivado em cache divergente: '+name)


def collect(output=DEFAULT_OUTPUT,root=DATA):
    output=Path(output);root=Path(root);output.mkdir(parents=True,exist_ok=True)
    jobs=[];records=[];seen=set()
    sides=sorted(p for name in ('reforma-historico','retencoes-defesa-setores') for p in (root/name).rglob('metadados.json'))
    for side in sides:
        source=json.loads(side.read_bytes())
        for item in source.get('originais',[]):
            original=Path(item['arquivo']);suffix=original.suffix.lower()
            if suffix not in ('.doc','.docx','.jpg','.jpeg','.png','.tif','.tiff','.bmp'):continue
            if digest(original)!=item['sha256']:raise ValueError('Original divergente: '+str(original))
            sid=str(source['source_id'])+'-'+original.stem
            identity=(sid,item['sha256'])
            if identity in seen:continue
            seen.add(identity)
            target=output/sid/item['sha256'];target.mkdir(parents=True,exist_ok=True)
            meta_path=target/'metadados.json'
            if meta_path.exists():
                meta=json.loads(meta_path.read_bytes());verify(target,meta);records.append(meta);continue
            kind='word' if suffix in ('.doc','.docx') else 'ocr'
            dest=target/('convertido.html' if kind=='word' else 'ocr.txt')
            jobs.append(dict(id=sid,original=str(original.resolve()),output=str(dest.resolve()),kind=kind,
                target=str(target.resolve()),source=item,origem_meta=str(side.resolve()),coletado_original=source['coletado_em']))
    jobs_path=output/'jobs.json';jobs_path.write_bytes(json.dumps(jobs,ensure_ascii=False,indent=2).encode())
    report_path=output/'conversao.json';errors=[]
    if jobs:
        previous=json.loads(report_path.read_bytes()) if report_path.exists() else []
        if isinstance(previous,dict):previous=[previous]
        reusable={r.get('output'):r for r in previous if r.get('status')=='convertido' and Path(r.get('output','')).is_file()}
        pending=[j for j in jobs if j['output'] not in reusable]
        jobs_path.write_bytes(json.dumps(pending,ensure_ascii=False,indent=2).encode())
        process=subprocess.run([str(POWERSHELL),'-NoProfile','-File',str(Path(__file__).with_name('extrair_legados.ps1')),
            '-JobsPath',str(jobs_path.resolve()),'-ReportPath',str(report_path.resolve())],capture_output=True,text=True,timeout=3600) if pending else None
        if process is not None and process.returncode:errors.append(dict(etapa='ferramenta_local',erro=(process.stderr or process.stdout)[-3000:]))
        result=json.loads(report_path.read_bytes()) if pending and report_path.exists() else []
        if isinstance(result,dict):result=[result]
        results={**reusable,**{r.get('output',r['id']):r for r in result}}
        image_jobs=[]
        for job in jobs:
            if job['kind']!='word' or results.get(job['output'],results.get(job['id'],{})).get('status')!='convertido':continue
            target=Path(job['target']);html=Path(job['output'])
            soup=BeautifulSoup(html.read_bytes(),'html.parser')
            for number,node in enumerate(soup.find_all('img',src=True),1):
                image=(target/node['src']).resolve()
                if not image.is_relative_to(target.resolve()) or not image.is_file():continue
                ocr_output=target/f'ocr-imagem-{number:03d}.txt'
                if not ocr_output.exists():image_jobs.append(dict(id=job['id']+f'-imagem-{number}',kind='ocr',original=str(image),output=str(ocr_output)))
        if image_jobs:
            ip=output/'ocr-suporte-jobs.json';ip.write_bytes(json.dumps(image_jobs,ensure_ascii=False).encode())
            subprocess.run([str(POWERSHELL),'-NoProfile','-File',str(Path(__file__).with_name('extrair_legados.ps1')),
                '-JobsPath',str(ip.resolve()),'-ReportPath',str((output/'ocr-suporte-resultados.json').resolve())],capture_output=True,text=True,timeout=1200)
        for job in jobs:
            target=Path(job['target']);r=results.get(job['output'],results.get(job['id'],{}))
            try:
                if r.get('status')!='convertido':raise ValueError(r.get('erro','Sem resultado da ferramenta'))
                intermediate=Path(job['output']);ocr_images=list(target.glob('ocr-imagem-*.txt'))
                try:body,stats=render(intermediate.read_bytes(),job['kind'],job['source']['source_url'])
                except ValueError:
                    if not ocr_images:raise
                    body='';stats={'extrator':'Microsoft Word HTML filtrado + Windows.Media.Ocr','tabelas':0}
                for image_text in ocr_images:
                    try:ocr_body,_=render(image_text.read_bytes(),'ocr',job['source']['source_url'])
                    except ValueError:
                        stats['imagens_sem_texto_ocr']=stats.get('imagens_sem_texto_ocr',0)+1
                        continue
                    body+='\n\n## OCR de imagem incorporada\n\n'+ocr_body
                if not body.strip():raise ValueError('Documento e imagens sem texto recuperável')
                if ocr_images:stats.update(imagens_ocr=len(ocr_images),ocr_revisao_pendente=True)
                content=('# Anexo recuperado — '+job['id']+'\n\nFonte: '+job['source']['source_url']+'\n\n> Derivado de original preservado. Conversão não certifica fidelidade, vigência ou aplicabilidade; revisão humana pendente.\n\n'+body+'\n').encode()
                md=target/'documento.md';md.write_bytes(content)
                meta=dict(source_id=job['id'],source_url=job['source']['source_url'],sha256=job['source']['sha256'],originais=[job['source']],
                    coletado_em=job['coletado_original'],extraido_em=datetime.now(timezone.utc).isoformat(),status='ocr_extraido_revisao_pendente' if job['kind']=='ocr' or ocr_images else 'extraido',
                    tipo='anexo_convertido',camada='A',vigencia='nao_verificada',revisao_humana='pendente',markdown_sha256=digest(md),origem_metadados=job['origem_meta'],
                    **stats,artefatos_sha256={p.relative_to(target).as_posix():digest(p) for p in target.rglob('*') if p.is_file()})
                (target/'metadados.json').write_bytes(json.dumps(meta,ensure_ascii=False,indent=2).encode());records.append(meta)
                print(job['id'],meta['status'],flush=True)
            except (ValueError,OSError,UnicodeError) as exc:errors.append(dict(id=job['id'],erro=str(exc)))
    manifest=dict(executado_em=datetime.now(timezone.utc).isoformat(),total=len(records)+sum('id' in e for e in errors),
        extraidos=len(records),word=sum(r.get('extrator','').startswith('Microsoft') for r in records),ocr=sum(r.get('extrator')=='Windows.Media.Ocr' for r in records),falhas=errors,
        documentos=records,limites='Recuperação de Word e imagens das coleções reforma-historico e retencoes-defesa-setores. Originais preservados; versões anteriores continuam indicando pendência histórica, com resolução nesta frente. OCR e tabelas requerem revisão humana.')
    (output/'manifesto.json').write_bytes(json.dumps(manifest,ensure_ascii=False,indent=2).encode())
    text='# Recuperação de anexos legados\n\n'+manifest['limites']+'\n\nExtraídos: '+str(len(records))+'.\n\n'
    text+='\n'.join('- ['+str(r['source_id'])+']('+str(r['source_id'])+'/'+r['sha256']+'/documento.md)' for r in records)+'\n'
    (output/'indice.md').write_bytes(text.encode());return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);m=collect(p.parse_args().output)
    print(json.dumps({k:m[k] for k in ('total','extraidos','word','ocr','falhas')},ensure_ascii=False,indent=2))
