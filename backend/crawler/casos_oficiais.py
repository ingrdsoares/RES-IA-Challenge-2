"""Índice de trechos candidatos a exemplos, extraídos literalmente de manuais oficiais."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from .cnpj_df import digest

DATA=Path(__file__).resolve().parent/'data'
FRONTS=('manuais','mei','complemento-contabil','obrigacoes-avancadas','distrital-df','sped-complementar','notas-tecnicas-fiscais')


def excerpts(text):
    lines=text.splitlines(); result=[];page=None;until=-1
    for i,line in enumerate(lines):
        if re.match(r'^#{1,6}\s+P[áa]gina\s+\d+',line,re.I):page=line.lstrip('# ').strip()
        if i<=until or not re.search(r'\bexemplo(?:s)?\b',line,re.I):continue
        # A local index or cross-reference alone is not a worked example.
        if len(line)>220 or re.search(r'\.{3,}|sumário|índice',line,re.I):continue
        end=min(i+70,len(lines))
        for j in range(i+2,end):
            if re.match(r'^#{1,6}\s+(?:P[áa]gina|Exemplo)',lines[j],re.I):end=j;break
        block='\n'.join(lines[i:end])
        if not re.search(r'R\$|\d[.,]\d|\d\s*%',block):continue
        result.append(dict(linha_inicio=i+1,linha_fim=end,pagina=page,texto=block))
        until=end-1
    return result


def collect(root=DATA):
    root=Path(root);output=root/'casos-oficiais';output.mkdir(parents=True,exist_ok=True);records=[];sources=0;seen=set()
    for front in FRONTS:
        for mp in sorted((root/front).rglob('metadados.json')):
            meta=json.loads(mp.read_bytes());originals=meta.get('originais')
            if not originals:
                candidates=list(mp.parent.glob('original.*'))
                originals=[dict(arquivo=str(p.resolve()),source_url=meta['source_url'],sha256=digest(p),bytes=p.stat().st_size) for p in candidates]
            if not originals:continue
            for md in mp.parent.glob('*.md'):
                if md.name in ('indice.md','tabelas.md'):continue
                text=md.read_text(encoding='utf-8-sig');cases=excerpts(text)
                if not cases:continue
                checksum=digest(md)
                if checksum in seen:continue
                seen.add(checksum);sources+=1;target=output/checksum
                source_md=dict(arquivo=str(md.resolve()),source_url=meta['source_url'],sha256=checksum,bytes=md.stat().st_size)
                content='# Candidatos a exemplos oficiais\n\nExtração literal do Markdown de origem. Seleção automática; pode conter referências ou exemplos incompletos. Não constitui cálculo validado nem caso de teste certificado. Confira o original.\n\n'
                for n,r in enumerate(cases,1):
                    content+=f"## Candidato {n} — linhas {r['linha_inicio']}–{r['linha_fim']}\n\nFonte: {md.relative_to(root).as_posix()} · {r['pagina'] or 'página não identificada'}\n\n"+r['texto']+'\n\n'
                    records.append(dict(fonte=md.relative_to(root).as_posix(),source_url=meta['source_url'],source_sha256=checksum,candidato=n,**{k:v for k,v in r.items() if k!='texto'}))
                raw=content.encode();target.mkdir(parents=True,exist_ok=True);dest=target/'documento.md';side=target/'metadados.json'
                if side.exists():
                    old=json.loads(side.read_bytes())
                    if dest.read_bytes()!=raw or digest(dest)!=old['markdown_sha256']:raise ValueError('Cache divergente de exemplos')
                else:
                    dest.write_bytes(raw)
                    side.write_bytes(json.dumps(dict(source_id='exemplos-'+checksum,source_url=meta['source_url'],sha256=checksum,
                        coletado_em=datetime.now(timezone.utc).isoformat(),originais=originals+[source_md],markdown_sha256=hashlib.sha256(raw).hexdigest(),
                        status='candidatos_extraidos',camada='B',revisao_humana='pendente',vigencia='nao_verificada',candidatos=len(cases),
                        limite='Trechos literais do derivado, selecionados automaticamente; não são exemplos novos nem casos certificados.'),ensure_ascii=False,indent=2).encode())
    manifest=dict(documentos_fonte=sources,candidatos=len(records),registros=records,limite='Enriquecimento derivado, não novos documentos oficiais; revisão obrigatória.')
    (output/'manifesto.json').write_bytes(json.dumps(manifest,ensure_ascii=False,indent=2).encode())
    links=sorted({r['source_sha256'] for r in records})
    (output/'indice.md').write_bytes(('# Exemplos oficiais — candidatos\n\n'+str(len(records))+' trechos em '+str(sources)+' arquivos Markdown de origem. Não são casos de teste certificados.\n\n'+'\n'.join(f'- [Fonte {h[:12]}]({h}/documento.md)' for h in links)+'\n').encode())
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=DATA);m=collect(p.parse_args().data)
    print(json.dumps({k:m[k] for k in ('documentos_fonte','candidatos')},ensure_ascii=False))
