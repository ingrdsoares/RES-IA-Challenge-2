"""Retentativas públicas limitadas; resultados históricos permanecem intactos."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib,json
from pathlib import Path
import httpx
from . import documentos_jurisprudencia as dj

DATA=Path(__file__).parent/'data'
OUTPUT=DATA/'fontes-recuperadas'
ALTERNATIVA='https://processo.stj.jus.br/docs_internet/informativos/PDF/Inf0872.pdf'

def candidates(previous):
    for item in previous['documentos']:
        if item.get('status')!='erro':continue
        if 'acordaos.economia.gov.br' in item['url']:yield item
        elif 'GetPDFINFJ?edicao=0872' in item['url']:
            yield {**item,'url':ALTERNATIVA,'url_anterior':item['url']}

def collect(output=OUTPUT):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    previous=json.loads((DATA/'documentos-jurisprudencia'/'manifesto.json').read_bytes())
    dj.ALLOWED.add('processo.stj.jus.br')
    def fetch(item):
        item={**item,'source_id':'recuperada-'+hashlib.sha256(item['url'].encode()).hexdigest()[:14]}
        item.pop('erro',None)
        try:
            with httpx.Client(timeout=45,follow_redirects=True) as client:
                r=client.get(item['url']);r.raise_for_status()
                if not dj.official(str(r.url)):raise ValueError('Redirecionamento fora de fonte oficial')
                result=dj.ingest(item,r.content,output)
        except Exception as exc:result={**item,'status':'erro','erro':str(exc)}
        print(item['titulo'],result['status'],flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,candidates(previous)))
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'extraidos':sum(r['status']=='extraido' for r in results),'documentos':results,'limites':'Retentativa única, timeout 45s, dois workers. Apenas seis PDFs CARF e URL pública alternativa do Informativo STJ 872; demais bloqueios SCON não contornados. Manifesto histórico preservado.'}
    (output/'manifesto.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Fontes recuperadas','',report['limites'],'','| Fonte | Estado |','|---|---|']
    for r in results:lines.append('| ['+r['titulo']+']('+r.get('markdown',r['url'])+') | '+r['status']+' |')
    (output/'indice.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    r=collect();print(json.dumps({k:r[k] for k in ('total','extraidos')},ensure_ascii=False))
