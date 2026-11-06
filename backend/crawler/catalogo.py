"""Catálogo local e auditoria de integridade; não valida conteúdo fiscal."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from .anexos import _cell, _write_atomic

FRONTES = {'MEI':'mei','CNPJ ampliado':'cnpj-ampliado','Tabelas fiscais':'tabelas-fiscais','Complemento contábil':'complemento-contabil','Indicadores IBGE':'ibge-indicadores','Sebrae':'sebrae','Auditoria':'catalogo','Notas explicativas CNAE':'notas-cnae','Consultas e divergências RFB':'consultas-rfb','Obrigações DCTFWeb/eSocial/Reinf':'obrigacoes-avancadas','Legislação complementar':'legislacao-complementar','ISS e NFS-e Distrito Federal':'distrital-df','Notas técnicas e classificações':'notas-tecnicas-fiscais','Regularização fiscal':'regularizacao-fiscal','Indicadores empresariais':'indicadores-empresariais','CNPJ Distrito Federal':'cnpj-df','XMLs de exemplo':'xmls-exemplo','Calendário DF 2026':'calendario-df','SPED complementar':'sped-complementar','IRPJ CSLL e lucro presumido':'tributacao-lucro','ICMS e consultas DF':'icms-consultas-df','Reforma e histórico CGSN':'reforma-historico','Documentos fiscais e jurisprudência':'documentos-jurisprudencia','CNPJ DF lotes completos':'cnpj-df-censo','Exemplos oficiais derivados':'casos-oficiais','Súmulas CARF e classificação':'sumulas-classificacao','Consultas e TARF DF ampliados':'consultas-df-amplas','Retenções defesa restituição e setores':'retencoes-defesa-setores','Anexos legados recuperados':'anexos-recuperados','Histórico por competência':'historico-competencias','Fontes recuperadas':'fontes-recuperadas','Normas centrais':'legislacao','Manuais Simples e MEI':'manuais','CNAE IBGE':'cnae','Anexos CGSN 140':'anexos-cgsn140','CNPJ tabelas auxiliares':'cnpj','Agenda federal inicial':'obrigacoes','Documentos fiscais iniciais':'documentos-fiscais','Contabilidade inicial':'contabilidade','Economia inicial':'economia','Reforma inicial':'reforma'}

def walk_files(root, *, with_stat=False):
    """Reuse directory-entry metadata instead of issuing a new stat for every path."""
    pending=[os.fspath(root)]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):pending.append(entry.path)
                elif entry.is_file():
                    path=Path(entry.path)
                    yield (path,entry.stat()) if with_stat else path


def frontmatter(text):
    if not text.startswith('---\n') and not text.startswith('---\r\n'):
        return None
    parts=re.split(r'^---\s*$',text,maxsplit=2,flags=re.M)
    if len(parts)<3:return None
    result={}
    for line in parts[1].splitlines():
        if ':' in line:
            key,value=line.split(':',1); result[key.strip()]=value.strip().strip('\"\'')
    return result

def allowed(path, root):
    parts=path.relative_to(root).parts
    return not any(p in ('inspection','catalogo','__pycache__') or p.startswith('.') or p.endswith('.tmp') for p in parts)

class Hasher:
    def __init__(self, cache=None):
        self.cache=cache or {}
        self.reads=0
    def digest(self,path):
        st=path.stat(); key=str(path.resolve()); signature=[st.st_size,st.st_mtime_ns,st.st_ctime_ns]
        old=self.cache.get(key)
        if old and old['stat']==signature:return old['sha256']
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
        result=h.hexdigest();self.cache[key]={'stat':signature,'sha256':result};self.reads+=1
        return result

def audit_snapshot(metadata,path,root,hasher):
    issues=[]
    source=metadata.get('source_url') or metadata.get('url')
    date=metadata.get('coletado_em')
    expected=metadata.get('sha256')
    for field,value in [('origem',source),('data',date),('hash',expected)]:
        if not value:issues.append('ausente_'+field)
    parent=path.parent
    multi=metadata.get('originais')
    candidates=sorted(parent.glob('original.*'))
    explicit=metadata.get('original')
    if explicit:
        target=parent/explicit
        candidates=[target] if target.is_file() and target.resolve().parent==parent.resolve() else []
    # Source ZIP is separate from extracted XSD. Only compare its own recorded hash.
    if not candidates and (parent/'fonte.zip').is_file():candidates=[parent/'fonte.zip']
    checks=[]
    if multi is not None:
        candidates=[]
        if not isinstance(multi,list) or not multi:
            issues.append('originais_lista_ausente')
        else:
            for item in multi:
                declared=item.get('sha256')
                original=Path(item.get('arquivo',''))
                original=original if original.is_absolute() else root/original
                try:
                    relative=original.resolve().relative_to(root.resolve())
                except ValueError:
                    issues.append('original_fora_raiz');continue
                if not original.is_file():
                    issues.append('original_ausente:'+str(relative));continue
                actual=hasher.digest(original)
                checks.append({'arquivo':str(relative).replace('\\','/'),'source_url':item.get('source_url'),'sha256_calculado':actual,'sha256_declarado':declared,'confere':actual==declared if declared else None})
                if not declared:issues.append('ausente_hash_original:'+str(relative))
                elif actual!=declared:issues.append('hash_divergente:'+str(relative))
                if not item.get('source_url'):issues.append('ausente_origem_original:'+str(relative))
                if item.get('bytes') is not None and original.stat().st_size!=item['bytes']:issues.append('tamanho_divergente:'+str(relative))
    for original in candidates:
        actual=hasher.digest(original)
        checks.append({'arquivo':str(original.relative_to(root)).replace('\\','/'),'sha256_calculado':actual,'sha256_declarado':expected,'confere':actual==expected if expected else None})
    if not checks:issues.append('original_ausente')
    elif multi is None and expected and not any(c['confere'] for c in checks):issues.append('hash_divergente')
    zip_expected=metadata.get('detalhes',{}).get('zip_sha256')
    if zip_expected:
        archive=parent/'fonte.zip'
        if not archive.is_file():issues.append('zip_fonte_ausente')
        else:
            actual=hasher.digest(archive)
            checks.append({'arquivo':str(archive.relative_to(root)).replace('\\','/'),'sha256_calculado':actual,'sha256_declarado':zip_expected,'confere':actual==zip_expected})
            if actual!=zip_expected:issues.append('hash_zip_divergente')
    markdown_expected=metadata.get('markdown_sha256')
    if markdown_expected:
        markdown=parent/metadata.get('markdown_arquivo','documento.md')
        if not markdown.is_file():issues.append('markdown_ausente')
        else:
            actual=hasher.digest(markdown)
            checks.append({'arquivo':str(markdown.relative_to(root)).replace('\\','/'),'tipo':'derivado_markdown','sha256_calculado':actual,'sha256_declarado':markdown_expected,'confere':actual==markdown_expected})
            if actual!=markdown_expected:issues.append('hash_markdown_divergente')
    return {'diretorio':str(parent.relative_to(root)).replace('\\','/'),'metadados':str(path.relative_to(root)).replace('\\','/'),'origem':source,'coletado_em':date,'sha256':expected,'status_fonte':metadata.get('status'),'revisao_humana':metadata.get('revisao_humana',metadata.get('revisao','nao_informada')),'vigencia':metadata.get('vigencia','nao_verificada'),'verificacoes':checks,'problemas':issues,'validacao_semantica':'nao_realizada'}

def manifest_entries(value):
    if isinstance(value,list):
        for child in value:yield from manifest_entries(child)
    elif isinstance(value,dict):
        if value.get('status') in ('erro','error','falha') or value.get('erro') or value.get('error'):
            yield value
        for key,child in value.items():
            if key in ('historico','history'):continue
            if key in ('ultima_tentativa','ultima_tentativa_html') and value.get('status') in ('coletado','extraido'):continue
            if isinstance(child,(dict,list)):yield from manifest_entries(child)

def collect(root):
    root=Path(root);output=root/'catalogo';output.mkdir(parents=True,exist_ok=True)
    cache_path=output/'hash-cache.json'
    try:cache=json.loads(cache_path.read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError):cache={}
    hasher=Hasher(cache);records=[];issues=[];covered=set()
    files=[p for p in walk_files(root) if allowed(p,root)]
    for path in sorted(p for p in files if p.name=='metadados.json'):
        try:
            meta=json.loads(path.read_text(encoding='utf-8-sig')); records.append(audit_snapshot(meta,path,root,hasher));covered.add(path.parent)
        except (ValueError,TypeError,AttributeError,OSError) as exc:issues.append({'arquivo':str(path.relative_to(root)),'erro':str(exc)})
    for path in sorted(p for p in files if p.suffix=='.md' and p.parent not in covered):
        meta=frontmatter(path.read_text(encoding='utf-8-sig'))
        if meta:
            records.append(audit_snapshot(meta,path,root,hasher));covered.add(path.parent)
    orphans=[];cached_requests=[]
    for p in files:
        if not p.name.startswith('original.') or p.name.endswith('.receipt.json') or p.parent in covered:continue
        receipt=p.with_name(p.name+'.receipt.json')
        if receipt.exists():
            try:
                meta=json.loads(receipt.read_bytes())
                actual=hasher.digest(p)
                if not meta.get('source_url') or not meta.get('coletado_em') or meta.get('sha256')!=actual:raise ValueError('Recibo de cache incompleto ou divergente')
                cached_requests.append(dict(arquivo=p.relative_to(root).as_posix(),source_url=meta['source_url'],sha256=actual,coletado_em=meta['coletado_em'],tipo='requisicao_sem_snapshot_semantico'))
                continue
            except (ValueError,OSError,TypeError) as exc:issues.append(dict(arquivo=receipt.relative_to(root).as_posix(),erro=str(exc)))
        orphans.append(p.relative_to(root).as_posix())
    latest={}
    for path in (p for p in files if p.name=='manifesto.json'):
        category=path.relative_to(root).parts[0]
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            stamp=data.get('executado_em','') if isinstance(data,dict) else max((x.get('coletado_em','') for x in data if isinstance(x,dict)),default='')
            key=(stamp,path.stat().st_mtime_ns)
            if category not in latest or key>latest[category][0]:latest[category]=(key,path,data)
        except (ValueError,TypeError,AttributeError) as exc:issues.append({'arquivo':str(path.relative_to(root)),'erro':'manifesto ilegível: '+str(exc)})
    manifests=[]
    for category,(_,path,data) in sorted(latest.items()):
        errors=list(manifest_entries(data))
        manifests.append({'categoria':category,'arquivo':str(path.relative_to(root)).replace('\\','/'),'erros':errors,'quantidade_erros':len(errors),'status':data.get('status') if isinstance(data,dict) else None})
    by_hash=defaultdict(list)
    for record in records:
        for check in record['verificacoes']:by_hash[check['sha256_calculado']].append(check['arquivo'])
    duplicates=[{'sha256':h,'arquivos':sorted(set(paths)),'interpretacao':'conteúdo idêntico; duplicação pode ser legítima entre fontes/categorias'} for h,paths in by_hash.items() if len(set(paths))>1]
    coverage=[]
    for name,folder in FRONTES.items():
        subset=[r for r in records if r['diretorio'].split('/')[0]==folder]
        errors=sum(m['quantidade_erros'] for m in manifests if m['categoria']==folder)
        pending=sum(r['status_fonte'] in ('ocr_pendente','dependencias_pendentes','anexos_pendentes','sem_exemplos','parcial') for r in subset)
        status=next((m['status'] for m in manifests if m['categoria']==folder),None)
        if folder=='catalogo':situation='executada'
        elif status=='em_andamento':situation='coleta_em_andamento'
        elif status in ('parcial','erro','falha') or errors or pending or any(r['problemas'] for r in subset):situation='coletada_com_pendencias'
        else:situation='coletada_revisao_pendente' if subset else 'sem_snapshot'
        coverage.append({'frente':name,'pasta':folder,'snapshots':len(subset),'problemas_integridade':sum(bool(r['problemas']) for r in subset),'erros_manifesto_mais_recente':errors,'status_execucao':status,'pendencias_extracao':pending,'situacao':situation})
    result={'executado_em':datetime.now(timezone.utc).isoformat(),'limites':'Auditoria técnica local: hashes não comprovam autenticidade remota, completude jurídica, vigência ou correção semântica. Preserva snapshots históricos. Hash cache usa caminho, tamanho, mtime e ctime; apagar hash-cache.json para releitura integral. Cada arquivo distinto é lido no máximo uma vez por execução.','snapshots':records,'duplicacoes':duplicates,'originais_sem_metadados':orphans,'requisicoes_cache_sem_snapshot':cached_requests,'erros_leitura':issues,'manifestos_mais_recentes':manifests,'cobertura_frentes':coverage,'cobertura_sete_frentes':coverage,'arquivos_hasheados_nesta_execucao':hasher.reads}
    _write_atomic(output/'catalogo.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    _write_atomic(cache_path,json.dumps(hasher.cache,ensure_ascii=False,indent=2)+'\n')
    lines=['# Catálogo consolidado','',result['limites'],'',f'Snapshots: {len(records)}. Grupos de conteúdo duplicado: {len(duplicates)}. Originais sem metadados: {len(orphans)}.','','| Frente | Snapshots | Integridade com pendências | Erros na última execução | Situação |','| --- | --- | --- | --- | --- |']
    lines += ['| '+' | '.join(_cell(c[k]) for k in ('frente','snapshots','problemas_integridade','erros_manifesto_mais_recente','situacao'))+' |' for c in coverage]
    lines += ['','## Snapshots','','| Diretório | Origem | Hash | Pendências |','| --- | --- | --- | --- |']
    lines += ['| '+' | '.join(_cell(v) for v in [r['diretorio'],r['origem'] or '',r['sha256'] or '',', '.join(r['problemas']) or 'nenhuma técnica'])+' |' for r in records]
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    review=['# Revisão pendente','', 'A conferência de integridade não aprova regras fiscais. Revisão humana pendente permanece pendente; nenhuma validação semântica foi realizada.','', '## Integridade e metadados','']
    review += [f'- {r["diretorio"]}: {", ".join(r["problemas"])}' for r in records if r['problemas']] or ['- Nenhuma divergência técnica nos snapshots auditados.']
    review += ['', '## Falhas nos manifestos mais recentes','']
    review += [f'- {m["arquivo"]}: {json.dumps(e,ensure_ascii=False)}' for m in manifests for e in m['erros']] or ['- Nenhuma falha registrada nos manifestos auditados.']
    review += ['', '## Originais sem metadados','']+[f'- {p}' for p in orphans]
    review += ['', '## Conteúdo duplicado','']+[f'- `{d["sha256"]}`: '+', '.join(d['arquivos']) for d in duplicates]
    review += ['', '## Erros de leitura','']+[f'- {e["arquivo"]}: {e["erro"]}' for e in issues]
    _write_atomic(output/'revisao.md','\n'.join(review)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,default=Path(__file__).parent/'data')
    result=collect(parser.parse_args().data)
    print(json.dumps({'snapshots':len(result['snapshots']),'com_problemas':sum(bool(r['problemas']) for r in result['snapshots']),'duplicacoes':len(result['duplicacoes']),'originais_sem_metadados':len(result['originais_sem_metadados']),'hashes_lidos':result['arquivos_hasheados_nesta_execucao'],'cobertura':result['cobertura_frentes']},ensure_ascii=False,indent=2))
