"""Buscas oficiais delimitadas: retenções, defesa, restituição e atividades econômicas."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import httpx
from . import consultas_rfb as rfb
from .reforma_historico import ingest, parse_search

DEFAULT_OUTPUT = Path(__file__).resolve().parent/'data'/'retencoes-defesa-setores'
QUERIES = {
 'retencao-iss': '"Simples Nacional" AND ISS',
 'retencao-federal': '"Simples Nacional" AND retenção',
 'retencao-previdenciaria': '"Simples Nacional" AND previdenciária',
 'substituicao-tributaria': '"Simples Nacional" AND "substituição tributária"',
 'substituicao-tributaria-ampla': '"Simples Nacional" AND substituição',
 'fiscalizacao-autos': '"Simples Nacional" AND fiscalização',
 'multas-penalidades': '"Simples Nacional" AND multa',
 'defesa-impugnacao': 'impugnação',
 'defesa-recursos': '"Simples Nacional" AND recurso',
 'restituicao': '"Simples Nacional" AND restituição',
 'compensacao': '"Simples Nacional" AND compensação',
 'atividade-tecnologia': '"Simples Nacional" AND software',
 'atividade-saude': '"Simples Nacional" AND saúde',
 'atividade-construcao': '"Simples Nacional" AND construção',
 'atividade-alimentacao': '"Simples Nacional" AND alimentação',
 'atividade-comercio': '"Simples Nacional" AND comércio',
}

def discover(client, output, max_pages=3, max_docs=2000, delay=.1):
    found, reports, errors = {}, {}, []
    for theme, term in QUERIES.items():
        seen, expected = set(), None
        for page in range(1, max_pages+1):
            payload=rfb.search_payload(term,page)
            # All actual types: SC/SD plus IN, AD and other official normative acts.
            payload['tiposAtosSelecionados']=''
            try:
                raw=rfb.cached(client,output/'listagens'/theme/f'{page:04}.json','POST',rfb.SEARCH,payload=payload,delay=delay)
                data=parse_search(raw)
                totals=(data['quantidadeTotal'],data['quantidadePaginas'])
                if expected is not None and expected != totals:
                    raise ValueError('Totais alterados durante paginação')
                expected=totals
                ids={r['idAto'] for r in data['atos']}
                if seen & ids:
                    raise ValueError('Identidade repetida entre páginas')
                if not ids and page < totals[1]:
                    raise ValueError('Página vazia antes do término')
                seen |= ids
                for row in data['atos']:
                    if not isinstance(row.get('tipoAto'),dict) or not row['tipoAto'].get('siglaTipoAto'):
                        raise ValueError('Tipo real do ato ausente')
                    aid=row['idAto']
                    if aid not in found and len(found)>=max_docs:
                        continue
                    item=found.setdefault(aid,{'row':row,'temas':[]})
                    if theme not in item['temas']:
                        item['temas'].append(theme)
                selected=sum(theme in i['temas'] for i in found.values())
                reports[theme]={'termo':term,'tipos_solicitados':'todos','total_fonte':totals[0], 'paginas_fonte':totals[1], 'paginas_coletadas':page,'resultados_lidos':len(seen),'selecionados':selected,'truncada_por_paginas':page < totals[1], 'truncada_por_limite_global':selected < len(seen), 'completa':len(seen)==totals[0] and selected==len(seen)}
                if page>=totals[1]:
                    break
            except Exception as exc:
                errors.append({'tema':theme,'pagina':page,'erro':str(exc)})
                break
        rfb.save_json(output/'descoberta.json',{'pesquisas':reports,'falhas':errors,'unicos':len(found)})
    return found,reports,errors

def collect(output=DEFAULT_OUTPUT,max_pages=3,max_docs=2000,delay=.1):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    report={'executado_em':rfb.stamp(),'escopo':'Busca literal na base normativa RFB; pertinência e aplicação ao Simples dependem de revisão. Inclui atos históricos. Não é universo semântico completo nem prova de vigência.','limites':{'max_paginas_por_tema':max_pages,'tamanho_pagina':100,'max_documentos':max_docs,'workers_por_host':3},'coletados':0,'documentos_parciais':0,'falhas':[],'status':'em_andamento'}
    with httpx.Client(timeout=20,follow_redirects=True) as client:
        found,searches,errors=discover(client,output,max_pages,max_docs,delay)
        report.update(pesquisas=searches,encontrados_unicos=len(found),falhas=errors)
        def work(item):
            try:
                meta=ingest(client,output,item,delay)
                meta['tipo_ato_fonte']=item['row']['tipoAto']
                sigla=item['row']['tipoAto']['siglaTipoAto']
                if sigla in ('SC','SD','SCI','ADI','Parec. Norm.'):
                    meta.update(tipo='interpretacao_administrativa',camada='B')
                elif sigla == 'Recom.':
                    meta.update(tipo='orientacao_oficial',camada='C')
                elif sigla not in ('IN','Resol.','Port.','Port. Norm.','Port. Conj.','Ato Conj.','AT Conj.','OS'):
                    meta.update(tipo='ato_administrativo',camada='B')
                meta['criterio_inclusao']='resultado de pesquisa literal oficial; pertinência humana pendente'
                meta['frentes']=[5 if t.startswith(('retencao','substituicao')) else 6 if t.startswith(('fiscalizacao','multas','defesa')) else 7 if t in ('restituicao','compensacao') else 8 for t in item['temas']]
                rfb.save_json(output/str(meta['source_id'])/'metadados.json',meta)
                return meta,None
            except Exception as exc:
                return None,{'id':item['row']['idAto'],'erro':str(exc)}
        with ThreadPoolExecutor(max_workers=3) as pool:
            for meta,error in pool.map(work,found.values()):
                if error: report['falhas'].append(error)
                else:
                    report['coletados']+=1
                    report['documentos_parciais']+=bool(meta['falhas'])
                rfb.save_json(output/'manifesto.json',report)
    metas=[json.loads(p.read_bytes()) for p in output.glob('*/metadados.json')]
    report['originais_preservados']=sum(len(m['originais']) for m in metas)
    report['bytes_originais']=sum(o['bytes'] for m in metas for o in m['originais'])
    report['cobertura_coletada']={t:sum(t in m['temas'] for m in metas) for t in QUERIES}
    report['status']='parcial' if report['falhas'] or report['documentos_parciais'] or any(not r['completa'] for r in searches.values()) else 'coleta_concluida'
    rfb.save_json(output/'manifesto.json',report)
    (output/'indice.md').write_text('# Retenções, defesa, restituição e atividades\n\n'+report['escopo']+'\n\n[Limites e falhas](manifesto.json)\n\n'+'\n'.join(f"- [{m['titulo']}]({m['source_id']}/documento.md) — {', '.join(m['temas'])}" for m in metas),encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--max-pages',type=int,default=3)
    parser.add_argument('--max-docs',type=int,default=2000)
    args=parser.parse_args()
    if args.max_pages<1 or args.max_docs<1: parser.error('Limites devem ser positivos')
    print(json.dumps(collect(args.output,args.max_pages,args.max_docs),ensure_ascii=False,indent=2))
