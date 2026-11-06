"""Pacote de continuidade sem credenciais, ambiente virtual ou acervo bruto."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import zipfile

REPO=Path(__file__).resolve().parents[2]
FORBIDDEN={'.git','.venv','venv','__pycache__','.pytest_cache'}

def digest(raw):return hashlib.sha256(raw).hexdigest()

def package(repo,output,state_path):
    repo=Path(repo).resolve();output=Path(output).resolve();state_path=Path(state_path)
    state=json.loads(state_path.read_bytes())
    if not state.get('run_id'):raise ValueError('Estado sem execução autoritativa')
    files=set()
    def add(path):
        path=Path(path)
        if not path.is_file():return
        relative=path.resolve().relative_to(repo)
        if any(x in FORBIDDEN or x=='.env' or x.startswith('.env.') for x in relative.parts):raise ValueError('Arquivo proibido no pacote')
        files.add(relative)
    for name in ('README.md','.gitignore','base_tributaria_ia_fontes_e_arquitetura.md','backend/README.md','backend/crawler/data/catalogo/catalogo.json','backend/crawler/data/estatisticas/totais.json'):
        add(repo/name)
    for directory in ('backend/refino','backend/crawler','backend/api'):
        folder=repo/directory
        if not folder.exists():continue
        for path in folder.rglob('*'):
            rel=path.relative_to(folder)
            if 'data' in rel.parts or any(x in FORBIDDEN for x in rel.parts):continue
            if path.suffix in ('.py','.md','.sql') or path.name in ('requirements.txt','Dockerfile','.gitignore','politica.json','extrair_legados.ps1'):add(path)
    for name in ('arquitetura-refino.md','crawler-arquitetura.md','arquitetura.md','refino-validacao.json','sumarizacao-acervo-tributario.md','exploracao-dados.md','guia_de_apis_fiscais_e_documenta_o.md'):
        add(repo/'docs'/name)
    for directory in ('docs/referencias-acervo','handoff/refino'):
        folder=repo/directory
        if folder.exists():
            for path in folder.rglob('*'):
                if path.suffix in ('.md','.json'):add(path)
    for name in ('docs/superpowers/specs/2026-11-05-refino-acervo-design.md','docs/superpowers/plans/2026-11-05-refino-inicial.md'):add(repo/name)
    run=repo/'backend/refino/data'/state['run_id']
    if not run.resolve().is_relative_to(repo/'backend/refino/data'):raise ValueError('Execução fora da pasta de refino')
    if not (run/'manifesto.json').is_file():raise ValueError('Execução autoritativa não encontrada')
    for path in run.rglob('*'):
        if path.suffix in ('.json','.jsonl','.md'):add(path)
    payloads={str(p).replace('\\','/'):(repo/p).read_bytes() for p in sorted(files)}
    manifest=dict(formato='handoff-refino-v1',criado_em=datetime.now(timezone.utc).isoformat(),run_id=state['run_id'],
        entrada='handoff/refino/CONTINUAR.md',dados_brutos_incluidos=False,textos_refinados_incluidos=True,
        limite='Pacote de código, estado, índices e referências. Inclui o snapshot refinado completo, com textos. Não contém os 10,429 GiB brutos. A reprodução integral requer os dados externos descritos no estado.',
        arquivos={name:dict(sha256=digest(raw),bytes=len(raw)) for name,raw in payloads.items()})
    run_manifest=json.loads(payloads[run.relative_to(repo).as_posix()+'/manifesto.json'])
    if run_manifest.get('run_id')!=state['run_id'] or not isinstance(run_manifest.get('artefatos_sha256'),dict):raise ValueError('Manifesto refinado incompatível/incompleto')
    for name,checksum in run_manifest['artefatos_sha256'].items():
        path=run/name
        if not path.resolve().is_relative_to(run.resolve()):raise ValueError('Artefato fora da execução')
        member=path.relative_to(repo).as_posix()
        if member not in payloads or digest(payloads[member])!=checksum:raise ValueError('Snapshot refinado incompleto/corrompido: '+name)
    if run_manifest.get('pipeline_sha256'):
        code=payloads.get('backend/refino/pipeline.py')
        if code is None or digest(code)!=run_manifest['pipeline_sha256']:raise ValueError('Código não corresponde à execução refinada')
    payloads['MANIFESTO-HANDOFF.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode()
    if output.exists():raise FileExistsError('Pacote existente preservado: '+str(output))
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,raw in payloads.items():archive.writestr(name,raw)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('ZIP com erro CRC')
        for name,entry in manifest['arquivos'].items():
            if digest(archive.read(name))!=entry['sha256']:raise ValueError('Hash divergente: '+name)
    checksum=digest(output.read_bytes())
    output.with_suffix(output.suffix+'.sha256').write_text(checksum+'  '+output.name+'\n',encoding='utf8')
    return dict(arquivo=str(output),bytes=output.stat().st_size,sha256=checksum,arquivos=len(payloads),verificado=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    output=args.output or REPO/'exports'/('refino-handoff-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.zip')
    print(json.dumps(package(REPO,output,REPO/'handoff/refino/estado.json'),ensure_ascii=False,indent=2))
