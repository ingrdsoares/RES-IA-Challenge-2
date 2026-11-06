"""Recorte DF ativo de portes 01/03, com todos os lotes da competência."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile
import httpx
from .cnpj import DAV, PUBLIC_AUTH, download, _competence, _member
from .cnpj_ampliado import rows
from .cnpj_df import digest
from .anexos import _cell

DATA=Path(__file__).resolve().parent/'data'
DEFAULT_OUTPUT=DATA/'cnpj-df-censo'


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_bytes(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
    tmp.replace(path)


def select_establishments(path):
    selected={}; count=0
    for count,r in rows(Path(path),30,max_size=32*1024**3):
        if r[19]=='DF' and r[5]=='02':
            selected.setdefault(r[0],dict(cnpj=''.join(r[:3]),uf=r[19],situacao=r[5],municipio=r[20],
                matriz_filial=r[3],cnae_principal=r[11],cnaes_secundarios=r[12],linha=count))
    return selected,{'linhas':count,'raizes_df_ativas':len(selected)}


def select_companies(path,roots):
    selected={};count=0
    for count,r in rows(Path(path),7,max_size=32*1024**3):
        if r[0] in roots and r[5] in ('01','03'):
            selected[r[0]]=dict(razao_social=re.sub(r'(?<!\d)(?:\d{11}|\d{3}\.\d{3}\.\d{3}-\d{2})(?!\d)','[CPF omitido]',r[1]),
                porte=r[5],natureza_juridica=r[2],linha=count)
    return selected,{'linhas':count,'elegiveis':len(selected)}


def select_options(path,roots):
    selected={};count=0
    keys=['opcao_simples','data_opcao_simples','data_exclusao_simples','opcao_mei','data_opcao_mei','data_exclusao_mei']
    for count,r in rows(Path(path),7,max_size=32*1024**3):
        if r[0] in roots:selected[r[0]]=dict(zip(keys,r[1:]),linha=count)
    return selected,{'linhas':count,'encontrados':len(selected)}


def stage(path,source,parser,selector=None):
    checksum=digest(source)
    request={'source_sha256':checksum,'selecao':selector,'versao':1}
    receipt=path.with_suffix('.receipt.json')
    if path.exists() and receipt.exists():
        old=json.loads(receipt.read_bytes())
        if old['request']==request and digest(path)==old['sha256']:
            result=json.loads(path.read_bytes());return result['registros'],result['cobertura']
        raise ValueError('Checkpoint divergente; preservado: '+str(path))
    records,coverage=parser(source)
    save(path,dict(registros=records,cobertura=coverage))
    save(receipt,dict(request=request,sha256=digest(path)))
    return records,coverage


def collect(output=DEFAULT_OUTPUT,competencia='2026-10'):
    competencia=_competence(competencia);output=Path(output);base=output/competencia
    raw=DATA/'cnpj-ampliado'/competencia/'raw';raw.mkdir(parents=True,exist_ok=True)
    names=[f'Estabelecimentos{i}.zip' for i in range(10)]+[f'Empresas{i}.zip' for i in range(10)]+['Simples.zip']
    paths={n:raw/n for n in names}
    old=DATA/'inspection'/'Empresas1-2026-10.zip'
    if competencia=='2026-10' and old.exists():paths['Empresas1.zip']=old
    def acquire(name):
        path=paths[name]
        if not path.exists():
            with httpx.Client(auth=PUBLIC_AUTH,timeout=180,follow_redirects=True) as client:
                part=path.with_suffix('.part');download(client,DAV+competencia+'/'+name,part,max_bytes=3*1024**3);part.replace(path)
        with zipfile.ZipFile(path) as z:_member(z,32*1024**3)
        print('ZIP pronto:',name,flush=True)
    # Two simultaneous public downloads keep bandwidth bounded.
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(acquire,names))
    establishments={};coverage={}
    for n in names[:10]:
        r,c=stage(base/'checkpoints'/f'{n}.json',paths[n],select_establishments)
        coverage[n]=c
        for root,row in r.items():establishments.setdefault(root,dict(row,arquivo=n))
        print('Estabelecimentos:',n,len(establishments),flush=True)
    roots=set(establishments);selector=hashlib.sha256(''.join(sorted(roots)).encode()).hexdigest();companies={}
    for n in names[10:20]:
        r,c=stage(base/'checkpoints'/f'{n}.json',paths[n],lambda p:select_companies(p,roots),selector)
        coverage[n]=c
        for root,row in r.items():companies.setdefault(root,dict(row,arquivo=n))
        print('Empresas:',n,len(companies),flush=True)
    eligible=set(companies);selector=hashlib.sha256(''.join(sorted(eligible)).encode()).hexdigest()
    options,c=stage(base/'checkpoints'/'Simples.zip.json',paths['Simples.zip'],lambda p:select_options(p,eligible),selector)
    coverage['Simples.zip']=c
    originals=[dict(arquivo=str(paths[n].resolve()),source_url=DAV+competencia+'/'+n,sha256=digest(paths[n]),bytes=paths[n].stat().st_size) for n in names]
    identity=hashlib.sha256(json.dumps(dict(fontes=originals,versao=1),sort_keys=True).encode()).hexdigest()
    target=base/identity;mp=target/'metadados.json'
    if mp.exists():
        meta=json.loads(mp.read_bytes())
        for name,checksum in meta['artefatos_sha256'].items():
            if digest(target/name)!=checksum:raise ValueError('Derivado divergente: '+name)
    else:
        target.mkdir(parents=True,exist_ok=True)
        keys=['opcao_simples','data_opcao_simples','data_exclusao_simples','opcao_mei','data_opcao_mei','data_exclusao_mei']
        records=[]
        for root in sorted(eligible):
            e=establishments[root];c=companies[root];s=options.get(root)
            records.append(dict(cnpj_basico=root,**{k:v for k,v in e.items() if k not in ('linha','arquivo')},
                **{k:v for k,v in c.items() if k not in ('linha','arquivo')},
                registro_simples_encontrado=s is not None,**{k:s[k] if s else None for k in keys},
                origens=dict(estabelecimento=dict(arquivo=e['arquivo'],linha=e['linha']),empresa=dict(arquivo=c['arquivo'],linha=c['linha']),simples=dict(arquivo='Simples.zip',linha=s['linha']) if s else None)))
        save(target/'registros.json',records)
        files=['registros.json'];links=[]
        for start in range(0,len(records),5000):
            name=f'empresas-{start//5000+1:03d}.md';links.append(f'- [Empresas {start+1}–{min(start+5000,len(records))}]({name})')
            text='# Empresas DF — '+competencia+'\n\n| CNPJ | Razão social | Porte | CNAE | Simples | MEI |\n|---|---|---|---|---|---|\n'
            text+=''.join('| '+' | '.join(_cell(str(r[k] if r[k] is not None else 'não encontrado')) for k in ('cnpj','razao_social','porte','cnae_principal','opcao_simples','opcao_mei'))+' |\n' for r in records[start:start+5000])
            (target/name).write_bytes(text.encode());files.append(name)
        text='# CNPJ DF — recorte completo dos lotes\n\nCompetência '+competencia+'. Dez lotes de estabelecimentos e dez de empresas percorridos integralmente; estabelecimento ativo DF (02), empresa de porte 01/03; uma linha por raiz. Filiais adicionais não são registros distintos. Não inclui outros portes ou baixadas. Ausência no Simples não equivale a N. Sem contatos, endereços ou QSA nos derivados. Não substitui consulta cadastral atual.\n\n'+str(len(records))+' empresas.\n\n'+'\n'.join(links)+'\n'
        (target/'dados.md').write_bytes(text.encode());files.append('dados.md')
        meta=dict(source_id='cnpj_df_censo',source_url=DAV+competencia+'/',sha256=identity,coletado_em=datetime.now(timezone.utc).isoformat(),
            competencia=competencia,originais=originals,status='extraido',registros=len(records),raizes_df_ativas=len(roots),
            sem_empresa_elegivel=len(roots)-len(eligible),sem_registro_simples=len(eligible)-len(options),cobertura_lotes=coverage,
            revisao_humana='pendente',artefatos_sha256={n:digest(target/n) for n in files})
        save(mp,meta)
    save(base/'manifesto.json',dict(meta,snapshot=identity,status='coleta_concluida'))
    (output/'indice.md').write_bytes(('# CNPJ DF ampliado\n\n['+str(meta['registros'])+' empresas — '+competencia+']('+competencia+'/'+identity+'/dados.md)\n').encode())
    return meta


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--competencia',default='2026-10');args=parser.parse_args()
    m=collect(competencia=args.competencia);print(json.dumps({k:m[k] for k in ('registros','raizes_df_ativas','sem_registro_simples')},ensure_ascii=False))
