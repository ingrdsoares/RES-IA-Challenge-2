"""Coleta inicial da documentação técnica e dos schemas NF-e/NFS-e."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import httpx

from backend.crawler.anexos import _cell, _write_atomic
from backend.crawler.manuais import ingest as ingest_pdf
from backend.crawler.esquemas import ingest as ingest_xsd

SVRS='https://dfe-portal.svrs.rs.gov.br/Nfe/Documentos'
DOWNLOAD='https://dfe-portal.svrs.rs.gov.br/NFE/DownloadArquivoEstatico/'
NFSE='https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual'
SOURCES={
    'nfe-moc':{'title':'NF-e/NFC-e — MOC 7.00, Anexo I, leiaute e regras de validação',
        'url':DOWNLOAD+'?sistema=NFE&tipoArquivo=1&nomeArquivo=moc7-anexo-i-leiaute-e-rv.pdf',
        'catalog_url':SVRS,'format':'pdf','identity':['manual de orientacao','leiaute','nf e'],
        'kind':'especificacao_tecnica','camada':'A','publicador':'Portal NF-e / SVRS'},
    'nfe-xsd':{'title':'NF-e — Pacote PL_010c_NT2022_002v1.30',
        'url':DOWNLOAD+'?sistema=NFE&tipoArquivo=2&nomeArquivo=PL_010c_NT2022_002v1.30.zip',
        'catalog_url':SVRS,'format':'zip','identity_namespace':'http://www.portalfiscal.inf.br/nfe'},
    'nfse-manual':{'title':'NFS-e — Manual API contribuintes, Emissor Público, v1.2 (outubro/2025)',
        'url':NFSE+'/manual-contribuintes-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out2025.pdf',
        'catalog_url':NFSE,'format':'pdf','identity':['manual dos contribuintes','sistema nacional nfs e'],
        'kind':'especificacao_tecnica','camada':'A','publicador':'Portal Nacional da NFS-e'},
    'nfse-xsd':{'title':'NFS-e — Esquemas XSD v1.01-20260209',
        'url':NFSE+'/nfse-esquemas_xsd-v1-01-20260209.zip',
        'catalog_url':NFSE,'format':'zip','identity_namespace':'http://www.sped.fazenda.gov.br/nfse'},
}
DEFAULT_OUTPUT=Path(__file__).resolve().parent/'data'/'documentos-fiscais'


def collect(sources: list[str], output: Path, client: httpx.Client) -> dict:
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    for source in sources:
        info=SOURCES[source]
        try:
            response=client.get(info['url'])
            response.raise_for_status()
            if info['format']=='pdf':
                path=ingest_pdf(source,response.content,output,source_info=info)
            else:
                path=ingest_xsd(source,info,response.content,output)
            meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
            results.append({**meta,'markdown':path.relative_to(output).as_posix()})
        except (httpx.HTTPError,ValueError,OSError) as exc:
            results.append({'source_id':source,'titulo':info['title'],'source_url':info['url'],
                            'status':'erro','erro':str(exc)})
        print(f'{source}: {results[-1]["status"]}',flush=True)
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'total':len(results),'documentos':results}
    lines=['# Documentação técnica de NF-e/NFC-e e NFS-e','',
        '> Recorte inicial de fontes oficiais. Documentação, esquemas e notas técnicas podem ter versões e períodos de aplicação distintos. Revisão de compatibilidade e vigência pendente. O índice reflete a última execução; versões anteriores permanecem no disco.','',
        '| Fonte | Estado | Páginas | XSDs | Declarações |','|---|---|---|---|---|']
    for item in results:
        title=_cell(item['titulo'])
        link=f'[{title}]({item["markdown"]})' if 'markdown' in item else title
        lines.append(f'| {link} | {item["status"]} | {item.get("paginas", "")} | {item.get("arquivos_xsd", "")} | {item.get("declaracoes", "")} |')
    for item in results:
        if 'erro' in item:
            lines.extend(['',f'> Falha em {item["source_id"]}: {_cell(item["erro"])}'])
        if item.get('dependencias_ausentes'):
            lines.extend(['',f'> {item["source_id"]}: dependências ausentes; consultar os metadados.'])
    _write_atomic(output/'manifesto.json',json.dumps(report,ensure_ascii=False,indent=2))
    _write_atomic(output/'indice.md','\n'.join(lines)+'\n')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=[*SOURCES,'all'],default='all')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    try:
        with httpx.Client(timeout=90,follow_redirects=True,
                          headers={'User-Agent':'SocioDigital-Crawler/0.1'}) as client:
            report=collect(list(SOURCES) if args.source=='all' else [args.source],args.output,client)
        pending=sum(item['status']!='extraido' for item in report['documentos'])
        print(f'Fontes: {report["total"]}; pendências/erros: {pending}')
        print(f'Índice: {(args.output/"indice.md").resolve()}')
        return int(pending>0)
    except (ValueError,OSError) as exc:
        print(f'Falha na coleta técnica: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
