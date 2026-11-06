"""Refino local, conservador e reproduzível; não modifica a coleta bruta."""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from dataclasses import asdict,replace
from urllib.parse import urlsplit,urlunsplit,unquote_plus,parse_qs
from backend.crawler.catalogo import frontmatter
from backend.crawler.normas_id import identidade_titulo
from backend.refino import similaridade

BASE=Path(__file__).resolve().parent
DATA=BASE.parent/'crawler'/'data'
OUTPUT=BASE/'data'
VERSION='1'


def sha(raw):return hashlib.sha256(raw).hexdigest()

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')

def file_sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def load_policy(path=None,profile=None):
    policy=json.loads(Path(path or BASE/'politica.json').read_bytes())
    if profile is not None:policy['perfil']=profile
    if policy['perfil'] not in policy['perfis']:raise ValueError('Perfil desconhecido')
    return policy


def canonical_url(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:raise ValueError('URL primária inválida')
    host=p.hostname.lower()
    if p.port and (p.scheme,p.port) not in (('https',443),('http',80)):host+=':'+str(p.port)
    query='&'.join(part for part in p.query.split('&') if part and not unquote_plus(part.split('=',1)[0]).lower().startswith('utm_') and unquote_plus(part.split('=',1)[0]).lower() not in ('gclid','fbclid'))
    return urlunsplit((p.scheme.lower(),host,p.path or '/',query,p.fragment))


def identity(url):
    p=urlsplit(url)
    if p.hostname in ('normasinternet2.receita.fazenda.gov.br','normas.receita.fazenda.gov.br'):
        match=re.fullmatch(r'/api/consulta-externa/ato/(\d+)/(?:visao/[^/]+|anexo/(\d+))/?',p.path)
        if match:return 'rfb:anexo:'+match[1]+':'+match[2] if match[2] else 'rfb:ato:'+match[1]
        if p.path.endswith('/link.action') and parse_qs(p.query).get('idAto'):
            aid=parse_qs(p.query)['idAto'][0]
            if aid.isdigit():return 'rfb:ato:'+aid
        match=re.fullmatch(r'/consulta/externa/(\d+)/visao/[^/]+',p.fragment)
        if match:return 'rfb:ato:'+match[1]
    return 'url:'+canonical_url(url)


_JURISDICAO_HOST={'planalto.gov.br':'federal','camara.leg.br':'federal','senado.leg.br':'federal','receita.fazenda.gov.br':'federal','sinj.df.gov.br':'df','confaz.fazenda.gov.br':'confaz'}
_VISAO={'multivigente':'compilada','compilada':'compilada','original':'original'}
_TIPOS_UNICOS=('lei','lc','decreto','ec')  # numeração única por jurisdição; portaria/IN/ADE/resolução variam por órgão
_OMISSAO=re.compile(r'[(\[]?\s*(?:\.{3}|…|\*{3})\s*[)\]]?')
_VISAO_ORDEM={'compilada':0,'unica':1,'original':2}


def chave_documento(meta,source,title):
    """norma:<chave> só quando verificável; senão a identidade por URL/ato."""
    if meta.get('norma_chave'):return 'norma:'+meta['norma_chave']
    key=identity(source)
    if key.startswith('rfb:') or str(meta.get('natureza_documental') or meta.get('tipo'))!='legislacao' or not title:return key
    norma=identidade_titulo(str(title))
    host=(urlsplit(source).hostname or '').lower()
    jur=next((j for h,j in _JURISDICAO_HOST.items() if host==h or host.endswith('.'+h)),None)
    if not norma or not jur or norma.tipo not in _TIPOS_UNICOS or norma.ano is None or norma.jurisdicao not in ('indefinida',jur):return key
    return 'norma:'+replace(norma,jurisdicao=jur).chave


def normalize_text(text):
    text=unicodedata.normalize('NFC',text.lstrip('\ufeff').replace('\r\n','\n').replace('\r','\n'))
    info=frontmatter(text)
    if info and info.get('source_url') and info.get('sha256'):
        parts=re.split(r'^---\s*$',text,maxsplit=2,flags=re.M)
        text=parts[2] if len(parts)==3 else text
    return text.strip('\n')+'\n'


def searchable(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text).lower() if not unicodedata.combining(c))


def classify(meta,front,text,policy):
    kind=str(meta.get('natureza_documental') or meta.get('tipo') or meta.get('kind') or '')
    if meta.get('status') in ('erro','falha','error'):return 'revisao',['coleta_com_falha']
    if front in policy['familias_dados'] or kind in policy['tipos_dados'] or type(meta.get('arquivos_xsd')) is int:return 'dados_estruturados',['dataset_ou_schema_separado_do_corpus_textual']
    original=str(meta.get('original','')).lower()
    if original.endswith(('.csv','.xlsx','.xsd')):return 'dados_estruturados',['tabela_ou_schema_primario']
    if kind in policy['tipos_evidencia']:return 'evidencia',['indice_catalogo_ou_comparacao']
    if front=='casos-oficiais':return 'evidencia',['trecho_derivado_ja_rastreado_no_documento_fonte']
    if front=='historico-competencias' or 'historica' in kind or 'historico' in kind and 'agenda' in kind:return 'historico',['competencia_historica_explicita']
    if text is None:return 'revisao',['texto_a_classificar']
    if not text.strip():return 'evidencia',['sem_documento_textual']
    terms=searchable(str(meta.get('titulo') or meta.get('title') or '')+' '+text)
    signals=[t for t in policy['termos_nucleo'] if searchable(t) in terms]
    source_type=meta.get('tipo_ato_fonte')
    source_type=(source_type.get('siglaTipoAto') or source_type.get('nomeTipoAto')) if isinstance(source_type,dict) else source_type
    if searchable(str(source_type or '')).strip() in ('port. pes.','portaria pessoal'):
        return 'complementar',['ato_explicito_de_pessoal']
    profile=policy['perfis'][policy['perfil']]
    if profile['amplo']:
        if kind in ('modelo_peticao_sem_forca_normativa','resumo_editorial_jurisprudencial','ato_administrativo'):
            return 'complementar',['natureza_operacional_editorial_ou_administrativa']
        jurisdiction=searchable(str(meta.get('jurisdicao','')))
        if profile['prioriza_df'] and jurisdiction and jurisdiction not in ('df','distrito federal','federal','brasil','nacional','federal/sped'):
            return 'complementar',['jurisdicao_explicita_fora_do_foco_df']
        taxfronts=set(policy['familias_nucleo'])|{'consultas-rfb','retencoes-defesa-setores','reforma-historico','distrital-df','icms-consultas-df','consultas-df-amplas','sumulas-classificacao','notas-cnae','tributacao-lucro','legislacao-complementar','documentos-fiscais','documentos-jurisprudencia','notas-tecnicas-fiscais','sped-complementar','obrigacoes','obrigacoes-avancadas','regularizacao-fiscal','calendario-df','anexos-recuperados','fontes-recuperadas','complemento-contabil','contabilidade'}
        if front in taxfronts:return 'nucleo',['perfil_todos_regimes_df' if profile['prioriza_df'] else 'perfil_tributario_nacional','fonte_do_recorte_tributario']
        return 'revisao',['pertinencia_tributaria_a_confirmar']
    if front in policy['familias_nucleo']:return 'nucleo',['familia_dirigida_ao_simples_mei']+['termo:'+t for t in signals]
    if signals and kind not in ('modelo_peticao_sem_forca_normativa','resumo_editorial_jurisprudencial'):
        return 'nucleo',['pertinencia_textual_candidata']+['termo:'+t for t in signals]
    if front in ('consultas-rfb','retencoes-defesa-setores','reforma-historico','distrital-df','icms-consultas-df','consultas-df-amplas','sumulas-classificacao','notas-cnae','tributacao-lucro','legislacao-complementar','documentos-fiscais','documentos-jurisprudencia','notas-tecnicas-fiscais','sped-complementar','obrigacoes','obrigacoes-avancadas','regularizacao-fiscal','calendario-df','anexos-recuperados','fontes-recuperadas'):
        return 'complementar',['referencia_tributaria_sem_sinal_dirigido_suficiente']
    return 'revisao',['relevancia_a_confirmar']


def text_path(root,metadata_path,meta):
    if metadata_path.suffix.lower()=='.md':return metadata_path
    declared=meta.get('markdown_arquivo') or meta.get('markdown_file') or meta.get('markdown')
    if declared:
        p=Path(declared);candidates=[p] if p.is_absolute() else [metadata_path.parent/p,root/p,root/metadata_path.relative_to(root).parts[0]/p]
        for p in candidates:
            if p.resolve().is_relative_to(metadata_path.parent.resolve()) and p.is_file():return p
        raise ValueError('Markdown declarado ausente ou fora do snapshot')
    for name in ('documento.md','legislacao.md','pagina.md','conteudo.md','dados.md'):
        p=metadata_path.parent/name
        if p.is_file():return p
    return None


def load_occurrence(snapshot,root,policy):
    mp=root/snapshot['metadados']
    if not mp.resolve().is_relative_to(root):raise ValueError('Metadados fora da camada de coleta')
    meta_raw=mp.read_bytes()
    meta=json.loads(meta_raw) if mp.suffix=='.json' else frontmatter(meta_raw.decode('utf-8-sig'))
    source=meta.get('source_url') or meta.get('url') or snapshot.get('origem')
    front=mp.relative_to(root).parts[0]
    key=chave_documento(meta,source,meta.get('titulo') or meta.get('title'));did=sha(key.encode())
    category,reasons=classify(meta,front,None,policy)
    errors=list(snapshot.get('problemas',[]));text='';md=None;md_sha=None;quality=[]
    if category not in ('dados_estruturados','evidencia'):
        try:
            md=text_path(root,mp,meta)
            if md:
                raw=md.read_bytes();md_sha=sha(raw)
                if meta.get('markdown_sha256') and md_sha!=meta['markdown_sha256']:raise ValueError('Hash do Markdown divergente')
                text=normalize_text(raw.decode('utf-8-sig'))
                if not meta.get('markdown_sha256'):quality.append('hash_derivado_registrado_nesta_primeira_fotografia')
            category,reasons=classify(meta,front,text,policy)
        except (ValueError,OSError,UnicodeError) as exc:errors.append(str(exc));text=''
    if errors:category='revisao';reasons+=['integridade_ou_extracao_pendente']
    if 'ocr' in str(meta.get('status','')).lower() or meta.get('imagens_sem_texto_ocr'):quality.append('ocr_ou_imagens_exigem_revisao')
    if meta.get('status') in ('parcial','dependencias_pendentes','anexos_pendentes'):quality.append('extracao_parcial_na_fonte')
    content_id=sha(text.encode()) if text.strip() and not errors else None
    originals=meta.get('originais') or [dict(source_url=source,sha256=meta.get('sha256'))]
    raw_set=sorted({str(r.get('sha256')) for r in originals if r.get('sha256')})
    # Full text distinguishes versions; a primary raw hash alone never merges them.
    version_id=sha(encoded([did,content_id or ('snapshot:'+sha(meta_raw))]))
    oid=sha(encoded([snapshot['metadados'],sha(meta_raw),md_sha]))
    title=meta.get('titulo') or meta.get('title')
    if not title and text:
        first=re.search(r'^#\s+(.+)$',text,re.M);title=first[1] if first else None
    title=str(title or meta.get('source_id') or key)
    views=meta.get('visoes_fonte') or ([{'visao':meta.get('visao_fonte')}] if meta.get('visao_fonte') else [])
    visao=_VISAO.get(str(meta.get('visao_fonte') or ''),'unica')
    occurrence=dict(id=oid,documento_id=did,versao_id=version_id,chave_origem=key,titulo=title,frente=front,
        metadados_ref=snapshot['metadados'],hash_metadados=sha(meta_raw),markdown_ref=md.relative_to(root).as_posix() if md else None,
        visao=visao,hash_markdown=md_sha,source_url=source,originais=originals,coletado_em=meta.get('coletado_em'),
        natureza=str(meta.get('natureza_documental') or meta.get('tipo') or 'nao_informada'),visoes=views,
        vigencia=meta.get('vigencia','nao_verificada'),classificacao=category,motivos=reasons,qualidade=quality,erros=errors,
        conteudo_id=content_id,bytes_texto=len(text.encode()) if content_id else 0,hashes_originais=raw_set,revisao_semantica='pendente')
    dataset=None
    if category=='dados_estruturados':
        dataset=dict(id=oid,documento_id=did,versao_id=version_id,frente=front,source_url=source,metadados_ref=snapshot['metadados'],
            competencia=meta.get('competencia'),registros=meta.get('registros'),artefatos=meta.get('artefatos_sha256',{}),
            limite='Registro do dataset de origem; registros/partições não foram copiados nem recontados neste refino.')
    return occurrence,text,dataset


def verify_output(folder,manifest):
    for name,checksum in manifest['artefatos_sha256'].items():
        p=folder/name
        if not p.resolve().is_relative_to(folder.resolve()) or not p.is_file() or file_sha(p)!=checksum:raise ValueError('Saída refinada corrompida: '+name)


def write_jsonl(path,rows):
    with path.open('wb') as f:
        for row in rows:f.write(encoded(row)+b'\n')


def run(root=DATA,catalog_path=None,output=OUTPUT,policy_path=None,profile=None,workers=8):
    root=Path(root).resolve();output=Path(output).resolve();catalog_path=Path(catalog_path or root/'catalogo'/'catalogo.json')
    if output.is_relative_to(root):raise ValueError('Saída deve ficar fora da camada de coleta')
    if not 1<=workers<=16:raise ValueError('Concorrência local deve estar entre 1 e 16')
    catalog_raw=catalog_path.read_bytes();inventory=json.loads(catalog_raw);policy=load_policy(policy_path,profile)
    snapshots=inventory['snapshots']
    with ThreadPoolExecutor(max_workers=workers) as pool:loaded=list(pool.map(lambda s:load_occurrence(s,root,policy),snapshots))
    loaded.sort(key=lambda r:r[0]['id']);fingerprint=sha(encoded([r[0]['id'] for r in loaded]));policy_sha=sha(encoded(policy))
    code_sha=sha(Path(__file__).read_bytes());catalog_sha=sha(catalog_raw)
    run_id=sha(encoded([VERSION,code_sha,catalog_sha,fingerprint,policy_sha]));target=output/run_id
    if (target/'manifesto.json').exists():
        manifest=json.loads((target/'manifesto.json').read_bytes())
        expected={'run_id':run_id,'politica_sha256':policy_sha,'entrada_fingerprint':fingerprint,'catalogo_sha256':catalog_sha,'pipeline_sha256':code_sha,'ocorrencias':len(loaded)}
        if any(manifest.get(k)!=v for k,v in expected.items()):raise ValueError('Saída refinada incompatível com a entrada')
        verify_output(target,manifest);return manifest
    output.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.tmp-refino-',dir=output));(stage/'conteudos').mkdir()
    contents={};versions={};docs={};datasets=[];occurrences=[];doc_por_conteudo=defaultdict(set)
    priority={'nucleo':0,'complementar':1,'historico':2,'revisao':3,'dados_estruturados':4,'evidencia':5}
    for row,text,dataset in loaded:
        occurrences.append(row)
        if dataset:datasets.append(dataset)
        cid=row['conteudo_id']
        if cid:doc_por_conteudo[cid].add(row['documento_id'])
        if cid and cid not in contents:
            contents[cid]=dict(id=cid,arquivo='conteudos/'+cid+'.md',bytes=row['bytes_texto'],normalizacao='NFC+finais_de_linha+frontmatter_de_coleta')
            (stage/contents[cid]['arquivo']).write_bytes(text.encode())
        version=versions.setdefault(row['versao_id'],dict(id=row['versao_id'],visao=row['visao'],documento_id=row['documento_id'],conteudo_id=cid,ocorrencias=[],categorias=set(),hashes_originais=set(),qualidade=set(),revisao_semantica='pendente'))
        version['ocorrencias'].append(row['id']);version['categorias'].add(row['classificacao']);version['hashes_originais'].update(row['hashes_originais']);version['qualidade'].update(row['qualidade'])
        doc=docs.setdefault(row['documento_id'],dict(id=row['documento_id'],chave_origem=row['chave_origem'],titulos=set(),naturezas=set(),versoes=set(),ocorrencias=[],categorias=set()))
        doc['titulos'].add(row['titulo']);doc['naturezas'].add(row['natureza']);doc['versoes'].add(row['versao_id']);doc['ocorrencias'].append(row['id']);doc['categorias'].add(row['classificacao'])
    for v in versions.values():
        for key in ('categorias','hashes_originais','qualidade'):v[key]=sorted(v[key])
        v['classificacao']=min(v['categorias'],key=priority.get)
        v['indexavel_nucleo']=v['conteudo_id'] is not None and v['classificacao']=='nucleo'
    def lines(vid):return {l.strip() for l in (stage/contents[versions[vid]['conteudo_id']]['arquivo']).read_text(encoding='utf8').splitlines() if l.strip()}
    rowmap={r['id']:r for r in occurrences};indexes={k:[] for k in ('nucleo','complementar','historico','revisao')};relations=[]
    for doc in docs.values():
        for key in ('titulos','naturezas','versoes','categorias'):doc[key]=sorted(doc[key])
        def rank(vid):
            v=versions[vid];candidates=[rowmap[oid] for oid in v['ocorrencias']]
            return (priority[v['classificacao']],min(len(r['erros']) for r in candidates),len(v['qualidade']),_VISAO_ORDEM[v['visao']],-len(v['hashes_originais']),-size(vid),vid)
        def size(vid):return max(rowmap[oid]['bytes_texto'] for oid in versions[vid]['ocorrencias'])
        big=max(size(v) for v in doc['versoes'])
        def pick(vids):
            # Candidata a preferida só se tiver porte comparável ao maior texto do documento (um stub nunca vence).
            pool=[v for v in vids if size(v)>=policy['limiar_bytes_preferida']*big]
            return (min(pool,key=rank),False) if pool else (min(vids,key=lambda v:(-size(v),rank(v))),True)
        doc['representacao_preferida']=pick(doc['versoes'])[0]
        doc['fora_do_indice']=[dict(versao=v,motivo='em_revisao' if versions[v]['classificacao']=='revisao' else 'sem_texto_extraido') for v in doc['versoes'] if versions[v]['classificacao']=='revisao' or not versions[v]['conteudo_id']]
        doc['criterio_representacao']='Preferência técnica de extração; não significa versão vigente. Todas as versões permanecem em versoes.jsonl e ocorrencias.jsonl; o índice lista a preferida e as extras com conteúdo novo, e fora_do_indice registra o motivo das demais.'
        for category in indexes:
            vids=[vid for vid in doc['versoes'] if versions[vid]['classificacao']==category and (category=='revisao' or versions[vid]['conteudo_id'])]
            if not vids:continue
            best,partial=pick(vids);shown=vids;out=[]
            if category!='revisao':
                # Original fica fora do índice; outra extração entra se tiver >5% de linhas ausentes na preferida ou linha ausente com dígito (valor alterado).
                ref=lines(best);shown=[best]
                for v in sorted(vids):
                    if v==best:continue
                    if versions[v]['visao']=='original' and any(versions[w]['visao']=='compilada' for w in vids):out.append(dict(versao=v,motivo='original_com_compilada'));continue
                    mine=lines(v);new={l for l in mine-ref if not _OMISSAO.fullmatch(l)}
                    if new and (len(new)/len(mine)>policy['limiar_linhas_ausentes_versao_extra'] or any(c.isdigit() for l in new for c in l)):shown.append(v)
                    else:out.append(dict(versao=v,motivo='versao_sem_conteudo_novo'))
            indexes[category].append(dict(documento_id=doc['id'],titulos=doc['titulos'],versoes=shown,fora_do_indice=out,apenas_versao_parcial=partial,representacao_preferida=best,revisao_semantica='pendente'))
        if doc['chave_origem'].startswith('rfb:anexo:'):
            parent=sha(('rfb:ato:'+doc['chave_origem'].split(':')[2]).encode())
            if parent in docs:relations.append(dict(documento_id=doc['id'],relacionado_id=parent,tipo='anexo_de',evidencia='identificadores_explicitos_na_url_rfb'))
    for name,rows in [('documentos',docs.values()),('versoes',versions.values()),('ocorrencias',occurrences),('conteudos',contents.values()),('datasets',datasets),('relacoes',relations)]:
        write_jsonl(stage/(name+'.jsonl'),sorted(rows,key=lambda r:r.get('id') or encoded(r).decode()))
    for category,rows in indexes.items():write_jsonl(stage/('indice_'+category+'.jsonl' if category!='revisao' else 'fila_revisao.jsonl'),sorted(rows,key=lambda r:r['documento_id']))
    # Similaridade é relatório: lê só os textos já escritos e não altera índice nem documentos. CNPJ/dados não têm texto aqui.
    pares=similaridade.comparar({cid:stage/meta['arquivo'] for cid,meta in contents.items()},workers=workers,documentos=doc_por_conteudo,params=policy.get('similaridade'))
    write_jsonl(stage/'similaridade.jsonl',[asdict(par) for par in pares]);write_jsonl(stage/'suspeitos.jsonl',[asdict(par) for par in similaridade.suspeitos(pares)])
    (stage/'politica.json').write_bytes(encoded(policy)+b'\n')
    counts=Counter(r['classificacao'] for r in occurrences);text_count=sum(r['conteudo_id'] is not None for r in occurrences)
    report=dict(run_id=run_id,pipeline_versao=VERSION,perfil=policy['perfil'],politica_sha256=policy_sha,entrada_fingerprint=fingerprint,catalogo_sha256=catalog_sha,pipeline_sha256=code_sha,
        criado_em=datetime.now(timezone.utc).isoformat(),ocorrencias=len(occurrences),documentos_logicos=len(docs),versoes=len(versions),conteudos_unicos=len(contents),
        ocorrencias_textuais=text_count,duplicacoes_textuais_eliminadas=text_count-len(contents),ocorrencias_agrupadas_por_identidade=len(occurrences)-len(docs),
        documentos_com_multiplas_versoes=sum(len(d['versoes'])>1 for d in docs.values()),datasets=len(datasets),categorias_ocorrencias=dict(counts),
        indices_documentos={k:len(v) for k,v in indexes.items()},ocorrencias_com_erros=sum(bool(r['erros']) for r in occurrences),
        bytes_textuais_entrada=sum(r['bytes_texto'] for r in occurrences),bytes_conteudos_unicos=sum(c['bytes'] for c in contents.values()),
        limites='Classificação candidata; não certifica vigência ou aplicabilidade. Sem exclusão de originais, versões ou dados estruturados. Índice padrão: núcleo. Conteúdos diferentes permanecem como versões; dados são referenciados, não copiados.')
    lines=['# Refino do acervo','',report['limites'],'',f"Perfil: {report['perfil']}. Ocorrências: {report['ocorrencias']}; documentos lógicos: {report['documentos_logicos']}; versões: {report['versoes']}; conteúdos: {report['conteudos_unicos']}.",'', '| Categoria das ocorrências | Quantidade |','|---|---:|']
    lines+=['| '+k+' | '+str(v)+' |' for k,v in sorted(counts.items())]
    lines+=['','## Consulta padrão','',f"Núcleo candidato: {len(indexes['nucleo'])} documentos, em indice_nucleo.jsonl. Complementares, histórico e revisão têm índices próprios. Todas as ocorrências e suas fontes permanecem em ocorrencias.jsonl.",'', 'A redução de entradas no índice não representa liberação de espaço na camada bruta nem validação jurídica.']
    (stage/'indice.md').write_bytes(('\n'.join(lines)+'\n').encode())
    report['artefatos_sha256']={p.relative_to(stage).as_posix():file_sha(p) for p in stage.rglob('*') if p.is_file()}
    (stage/'manifesto.json').write_bytes(encoded(report)+b'\n')
    if stage.resolve().parent!=output or target.resolve().parent!=output:raise ValueError('Destino de publicação inválido')
    stage.rename(target)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=DATA);p.add_argument('--catalogo',type=Path);p.add_argument('--output',type=Path,default=OUTPUT);p.add_argument('--politica',type=Path);p.add_argument('--perfil');p.add_argument('--workers',type=int,default=8);a=p.parse_args()
    report=run(a.data,a.catalogo,a.output,a.politica,a.perfil,a.workers)
    print(json.dumps({k:v for k,v in report.items() if k!='artefatos_sha256'},ensure_ascii=False,indent=2))
