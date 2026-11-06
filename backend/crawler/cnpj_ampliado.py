"""Amostra cruzada dos arquivos públicos CNPJ, sem carregar os CSVs em memória."""
import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile
import httpx
from .cnpj import DAV, PUBLIC_AUTH, _member, _competence, download
from .anexos import _cell

DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'cnpj-ampliado'
FILES=('Estabelecimentos1.zip','Empresas2.zip','Simples.zip')

def rows(path, columns, *, max_size=8*1024**3):
    with zipfile.ZipFile(path) as archive:
        member=_member(archive,max_size)
        with archive.open(member) as stream:
            for number,row in enumerate(csv.reader(io.TextIOWrapper(stream,encoding='latin-1',newline=''),delimiter=';',strict=True),1):
                if len(row)!=columns:raise ValueError(f'{path.name}, linha {number}: esperado {columns} campos')
                yield number,row

def sample(raw, limit=100, candidates=1000):
    if not 1<=limit<=candidates<=10000:raise ValueError('Limites inválidos')
    establishments={}
    for line,row in rows(raw/FILES[0],30):
        if row[5]=='02' and row[0] not in establishments:
            establishments[row[0]]=(line,row)
            if len(establishments)==candidates:break
    companies={}
    for line,row in rows(raw/FILES[1],7):
        if row[0] in establishments:companies[row[0]]=(line,row)
        if len(companies)==len(establishments):break
    selected=[root for root in establishments if root in companies and companies[root][1][5] in ('01','03')][:limit]
    if len(selected)!=limit:raise ValueError(f'Apenas {len(selected)} empresas compatíveis; ampliar candidatos/lotes')
    selected_roots=set(selected)
    options={}
    for line,row in rows(raw/FILES[2],7):
        if row[0] in selected_roots:options[row[0]]=(line,row)
        if len(options)==len(selected):break
    result=[]
    for root in selected:
        el,e=establishments[root];cl,c=companies[root];sl,s=options.get(root,(None,None))
        result.append({'cnpj_basico':root,'cnpj':e[0]+e[1]+e[2],'razao_social':c[1],'porte':c[5],
          'situacao':e[5],'matriz_filial':e[3],'uf':e[19],'municipio':e[20],'cnae_principal':e[11],
          'cnaes_secundarios':e[12],'registro_simples_encontrado':s is not None,
          'opcao_simples':s[1] if s else None,'data_opcao_simples':s[2] if s else None,
          'data_exclusao_simples':s[3] if s else None,'opcao_mei':s[4] if s else None,
          'data_opcao_mei':s[5] if s else None,'data_exclusao_mei':s[6] if s else None,
          'linhas_origem':{'estabelecimentos':el,'empresas':cl,'simples':sl}})
    return result

def collect(output=DEFAULT_OUTPUT,competencia='2026-10',limit=100,candidates=1000):
    competencia=_competence(competencia);base=Path(output)/competencia;raw=base/'raw';raw.mkdir(parents=True,exist_ok=True)
    with httpx.Client(auth=PUBLIC_AUTH,timeout=120,follow_redirects=True) as client:
        for name in FILES:
            path=raw/name
            if not path.exists():
                temporary=path.with_suffix('.part');download(client,DAV+competencia+'/'+name,temporary,max_bytes=700*1024**2);temporary.replace(path)
    records=sample(raw,limit,candidates)
    originals=[]
    for name in FILES:
        with (raw/name).open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        originals.append({'arquivo':str((raw/name).resolve()),'source_url':DAV+competencia+'/'+name,'sha256':digest,'bytes':(raw/name).stat().st_size})
    identity=hashlib.sha256(json.dumps([originals,limit,candidates],sort_keys=True).encode()).hexdigest()
    target=base/identity;target.mkdir(parents=True,exist_ok=True)
    meta={'source_id':'cnpj_ampliado','source_url':DAV+competencia+'/', 'coletado_em':datetime.now(timezone.utc).isoformat(),
      'sha256':identity,'originais':originals,'competencia':competencia,'registros':len(records),'status':'extraido','revisao_humana':'pendente',
      'amostragem':f'Primeiros {candidates} estabelecimentos ativos distintos do lote 1; cruzamento Empresas2, portes 01/03; primeiros {limit} elegíveis.',
      'sem_registro_simples':sum(not r['registro_simples_encontrado'] for r in records)}
    (target/'registros.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'metadados.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    text='# CNPJ — amostra cruzada\n\n'+meta['amostragem']+'\n\nCompetência: '+competencia+'. Ausência no arquivo Simples não significa opção N. Datas e opções preservadas literalmente. A amostra não representa estatisticamente o Brasil. Contatos, endereços e QSA não são incluídos na extração; arquivos públicos originais integrais permanecem locais.\n\n| CNPJ | Razão social | UF | CNAE | Simples | MEI |\n|---|---|---|---|---|---|\n'
    for r in records:text+='| '+' | '.join(_cell(str(r[k] if r[k] is not None else 'não encontrado')) for k in ('cnpj','razao_social','uf','cnae_principal','opcao_simples','opcao_mei'))+' |\n'
    (target/'dados.md').write_text(text,encoding='utf-8')
    (base.parent/'indice.md').write_text(f'# CNPJ ampliado\n\n[{len(records)} registros cruzados]({competencia}/{identity}/dados.md) · [Metadados]({competencia}/{identity}/metadados.json)\n',encoding='utf-8')
    print(json.dumps({'registros':len(records),'sem_simples':meta['sem_registro_simples'],'destino':str(target)},ensure_ascii=False))
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--competencia',default='2026-10');parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args();collect(args.output,args.competencia)
