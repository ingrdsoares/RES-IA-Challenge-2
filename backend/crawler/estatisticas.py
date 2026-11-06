"""Estimativa reproduzível do acervo, sem somar unidades diferentes."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import hashlib
import zipfile
from pathlib import Path
import pypdfium2
from .catalogo import collect as catalog,Hasher,walk_files

DATA=Path(__file__).resolve().parent/'data'


def collect(root=DATA):
    root=Path(root);inventory=catalog(root);output=root/'estatisticas';output.mkdir(parents=True,exist_ok=True)
    file_entries=[(p,st) for p,st in walk_files(root,with_stat=True) if not any(x in ('catalogo','estatisticas','__pycache__') or x.endswith('.tmp') for x in p.relative_to(root).parts)]
    files=[p for p,st in file_entries]
    extensions=Counter();size=0;markdown_bytes=0;byfront={}
    for p,st in file_entries:
        length=st.st_size;size+=length;extensions[p.suffix.lower()]+=1
        front=p.relative_to(root).parts[0];entry=byfront.setdefault(front,dict(arquivos=0,bytes=0,markdown=0))
        entry['arquivos']+=1;entry['bytes']+=length
        if p.suffix.lower()=='.md':markdown_bytes+=length;entry['markdown']+=1
    originals={}
    for snapshot in inventory['snapshots']:
        for check in snapshot['verificacoes']:
            p=root/check['arquivo']
            if check.get('tipo')=='derivado_markdown' or p.suffix.lower()=='.md':continue
            checksum=check.get('sha256_calculado')
            if checksum:originals.setdefault(checksum,dict(arquivo=check['arquivo'],bytes=p.stat().st_size,extensao=p.suffix.lower()))
    roots=set();occurrences=0;json_errors=[]
    for p in files:
        if p.name!='registros.json':continue
        try:
            data=json.loads(p.read_bytes())
            if not isinstance(data,list):continue
            for row in data:
                if not isinstance(row,dict):continue
                root_id=row.get('cnpj_basico')
                if root_id:roots.add(str(root_id));occurrences+=1
        except (ValueError,OSError) as exc:json_errors.append(dict(arquivo=p.relative_to(root).as_posix(),erro=str(exc)))
    pages={};pdf_errors=[]
    # Metadata can reference a PDF more than once; count physical pages once per content hash.
    hasher=Hasher();pdf_files=0
    for p in files:
        if p.suffix.lower()!='.pdf':continue
        pdf_files+=1;checksum=hasher.digest(p)
        if checksum in pages:continue
        try:
            with pypdfium2.PdfDocument(p) as doc:pages[checksum]=len(doc)
        except Exception as exc:pdf_errors.append(dict(arquivo=p.relative_to(root).as_posix(),erro=str(exc)))
    schemas=set();schema_occurrences=0
    for p in files:
        if p.suffix.lower()=='.xsd':
            schemas.add(hasher.digest(p));schema_occurrences+=1
        elif p.suffix.lower()=='.zip':
            try:
                with zipfile.ZipFile(p) as archive:
                    for member in archive.infolist():
                        if not member.is_dir() and member.filename.lower().endswith('.xsd'):
                            if member.file_size>20*1024**2:raise ValueError('XSD excede 20MiB na contagem')
                            schemas.add(hashlib.sha256(archive.read(member)).hexdigest());schema_occurrences+=1
            except (ValueError,OSError,zipfile.BadZipFile,RuntimeError) as exc:
                pdf_errors.append(dict(arquivo=p.relative_to(root).as_posix(),erro=str(exc)))
    cnpj_reports=[]
    for p in (root/'cnpj-df-censo').rglob('manifesto.json'):
        m=json.loads(p.read_bytes())
        cnpj_reports.append(dict(competencia=m['competencia'],empresas=m['registros'],raizes_df_ativas=m['raizes_df_ativas'],linhas_percorridas=sum(v['linhas'] for v in m['cobertura_lotes'].values()),lotes=len(m['cobertura_lotes'])))
    cases=root/'casos-oficiais'/'manifesto.json'
    candidates=json.loads(cases.read_bytes()).get('candidatos',0) if cases.exists() else 0
    result=dict(executado_em=datetime.now(timezone.utc).isoformat(),snapshots=len(inventory['snapshots']),
        snapshots_com_problemas=sum(bool(r['problemas']) for r in inventory['snapshots']),
        originais_conteudos_distintos=len(originals),originais_distintos_por_extensao=dict(Counter(r['extensao'] for r in originals.values())),
        arquivos_em_disco=len(files),bytes_em_disco=size,gib_em_disco=round(size/1024**3,3),arquivos_por_extensao=dict(extensions),
        markdown_arquivos=extensions['.md'],markdown_bytes=markdown_bytes,pdf_arquivos=pdf_files,pdf_conteudos_distintos=len(pages),
        paginas_pdf_distintas=sum(pages.values()),empresas_raizes_distintas=len(roots),ocorrencias_empresas_derivados=occurrences,
        candidatos_exemplos=candidates,xsd_conteudos_distintos=len(schemas),xsd_ocorrencias_arquivos_e_pacotes=schema_occurrences,recortes_cnpj=cnpj_reports,por_pasta=byfront,erros_leitura=json_errors+pdf_errors,
        limites='Unidades não somáveis. Snapshots incluem versões e enriquecimentos. Conteúdos originais distintos são deduplicados por hash, incluindo JSON de catálogo e ZIP; não equivalem a normas distintas. Markdown inclui índices e trechos derivados. Páginas são físicas dos PDFs distintos legíveis, não garantia de extração de texto. Empresas distintas por raiz dos arquivos registros.json, não por estabelecimento nem por registro bruto dos ZIPs. Bytes incluem originais, históricos, checkpoints e arquivos parciais; excluem catálogo/estatísticas e temporários .tmp. Nenhuma estimativa de linhas de ZIP não percorridos.')
    (output/'totais.json').write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode())
    rows=[('Snapshots/versões catalogados',result['snapshots']),('Conteúdos originais distintos por hash',len(originals)),
          ('Arquivos Markdown (inclui índices)',extensions['.md']),('PDFs de conteúdo distinto',len(pages)),('Páginas físicas dos PDFs distintos',sum(pages.values())),
          ('Schemas XSD distintos (inclui pacotes ZIP)',len(schemas)),('Empresas distintas por raiz nos derivados',len(roots)),('Candidatos a exemplos (derivados)',candidates),('Arquivos locais',len(files)),('Volume local (GiB)',result['gib_em_disco'])]
    text='# Estimativa numérica do acervo\n\n'+result['limites']+'\n\n| Medida | Quantidade |\n|---|---:|\n'+''.join(f'| {label} | {value} |\n' for label,value in rows)
    text+='\n## Por pasta\n\n| Pasta | Arquivos | Markdown | Bytes |\n|---|---:|---:|---:|\n'+''.join(f"| {k} | {v['arquivos']} | {v['markdown']} | {v['bytes']} |\n" for k,v in sorted(byfront.items()))
    (output/'indice.md').write_bytes(text.encode());return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=DATA);m=collect(p.parse_args().data)
    print(json.dumps({k:v for k,v in m.items() if k not in ('por_pasta','limites','originais_distintos_por_extensao','arquivos_por_extensao')},ensure_ascii=False,indent=2))
