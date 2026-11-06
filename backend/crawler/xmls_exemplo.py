"""Inventário seguro de XMLs publicados explicitamente como exemplos oficiais.

Não consulta notas, não emite documentos e não valida assinaturas ou autorização fiscal.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import httpx
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from backend.crawler.anexos import _write_atomic
from backend.crawler.documentos_fiscais import SOURCES as TECHNICAL_SOURCES

DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'xmls-exemplo'
SOURCES = {
    'sp-nfse-exemplos': {
        'title': 'São Paulo — exemplos municipais de RPS e retornos NFS-e (2025)',
        'url': 'https://notadomilhao.sf.prefeitura.sp.gov.br/wp-content/uploads/2025/11/Arquivos-de-exemplo.zip',
        'catalog_url': 'https://notadomilhao.sf.prefeitura.sp.gov.br/wp-content/uploads/2026/01/NFe_Web_Service.pdf',
        'jurisdicao': 'São Paulo/SP; padrão municipal, incompatibilidade nacional/DF não avaliada',
        'namespace': 'http://www.prefeitura.sp.gov.br/nfe',
        'example': True,
    },
    **{k: {**TECHNICAL_SOURCES[k], 'example': False, 'namespace': TECHNICAL_SOURCES[k]['identity_namespace']}
       for k in ('nfe-xsd', 'nfse-xsd')},
}
DISCOVERY = [
    {'source_url': 'https://www2.manaus.am.gov.br/docs/portal/secretarias/semef/nfce/MOPS%20NFC-e%202020%20v1.10.pdf', 'escopo': 'Manual municipal NFC-e histórico 2020', 'resultado': 'Link público de exemplo https://1drv.ms/u/s!AkzEn2dWU2SWpxXbeIZY_gPtOBGw?e=gIBmLC retorna página HTML OneDrive; nenhum XML baixado ou autenticação utilizada.'},
    {'source_url': 'https://dfe-portal.svrs.rs.gov.br/Nfe/Documentos', 'escopo': 'NF-e/NFC-e 55/65 e eventos', 'resultado': 'Nenhum pacote de exemplos de instância identificado neste recorte; schemas não são notas.'},
    {'source_url': 'https://www.nfe.fazenda.gov.br/portal/principal.aspx', 'escopo': 'Portal Nacional NF-e', 'resultado': 'Sem XML de exemplo coletado; consultas de documentos fiscais não utilizadas.'},
    {'source_url': 'https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual', 'escopo': 'DPS/NFSe nacional', 'resultado': 'Pacote XSD inspecionado; zero XML de instância.'},
    {'source_url': 'https://iss.fazenda.df.gov.br/online/Default/PerguntasFrequentes.aspx', 'escopo': 'NFS-e DF', 'resultado': 'Referência ao manual do provedor e validador de homologação; nenhuma nota real consultada.'},
]


def package_members(raw: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(e.file_size for e in entries) > 50 * 1024 * 1024:
                raise ValueError('ZIP excede limites de entradas/tamanho.')
            names = set()
            result = {}
            for entry in entries:
                name = entry.filename.replace('\\', '/')
                if name.startswith('/') or ':' in name or '..' in PurePosixPath(name).parts or name in names:
                    raise ValueError('Caminho inseguro ou duplicado no ZIP.')
                names.add(name)
                if entry.file_size > 10 * 1024 * 1024:
                    raise ValueError('Entrada excede limite individual.')
                if not entry.is_dir() and name.lower().endswith(('.xml', '.txt')):
                    result[name] = archive.read(entry)
            return result
    except zipfile.BadZipFile as exc:
        raise ValueError('ZIP inválido.') from exc


def inventory(raw: bytes, expected_namespace: str) -> dict:
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise ValueError('XML inválido ou inseguro.') from exc
    namespace = root.tag[1:].split('}')[0] if root.tag.startswith('{') else ''
    if namespace != expected_namespace:
        raise ValueError('Namespace do XML não corresponde à fonte.')
    local = lambda tag: tag.rsplit('}', 1)[-1]
    fields = []
    values = {}
    def walk(node, path):
        if path.count('/') > 100:
            raise ValueError('XML excede profundidade máxima.')
        text = (node.text or '').strip()
        fields.append({'caminho': path, 'atributos': dict(node.attrib), 'valor': text if len(node) == 0 else None})
        if text:
            values.setdefault(local(node.tag), []).append(text)
        for child in node:
            walk(child, path + '/' + local(child.tag))
    walk(root, '/' + local(root.tag))
    model = next((m for m in values.get('mod', []) if m in ('55', '65')), None)
    national_nfe = namespace == 'http://www.portalfiscal.inf.br/nfe'
    if national_nfe and local(root.tag) in ('NFe', 'nfeProc', 'enviNFe') and model is None:
        raise ValueError('NF-e/NFC-e sem modelo 55/65 identificável.')
    kind = ('NFC-e' if model == '65' else 'NF-e') if model else local(root.tag)
    environments = sorted(set(values.get('tpAmb', [])))
    version = root.attrib.get('versao') or root.attrib.get('Versao')
    return {'raiz': local(root.tag), 'namespace': namespace, 'modelo': model, 'tipo_documento': kind,
            'versao': version, 'versoes_internas': sorted({f['atributos'][k] for f in fields for k in ('Versao', 'versao') if k in f['atributos']}),
            'tpAmb': environments, 'ambiente': 'homologacao' if environments == ['2'] else ('producao' if environments == ['1'] else 'nao_informado_ou_misto'),
            'campos': fields, 'xml_bem_formado': True,
            'validacao_xsd': 'nao_realizada: schema compatível não selecionado; exemplos SP não usam XSD nacional',
            'assinatura_validada': False, 'validade_fiscal': 'não avaliada; exemplo publicado não equivale a documento autorizado'}


def collect(sources: list[str], output: Path, client: httpx.Client) -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for source_id in sources:
        info = SOURCES[source_id]
        try:
            response = client.get(info['url'])
            response.raise_for_status()
            raw = response.content
            digest = hashlib.sha256(raw).hexdigest()
            folder = output / source_id / digest
            metadata_path = folder / 'metadados.json'
            if metadata_path.exists():
                cached = json.loads(metadata_path.read_text(encoding='utf-8'))
                original = folder / 'original.zip'
                if (original.exists() and hashlib.sha256(original.read_bytes()).hexdigest() == digest
                        and all(Path(d['arquivo']).is_file() and hashlib.sha256(Path(d['arquivo']).read_bytes()).hexdigest() == d['sha256'] for d in cached['documentos'])):
                    results.append(cached)
                    continue
            members = package_members(raw)
            docs = []
            for name, content in members.items():
                doc = inventory(content, info['namespace'])
                relative = Path('xml') / (name + '.xml')
                docs.append({**doc, 'nome_no_pacote': name, 'arquivo': (folder / relative).resolve().as_posix(), 'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)})
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'original.zip').write_bytes(raw)
            for doc, content in zip(docs, members.values()):
                path = Path(doc['arquivo'])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            meta = {'source_id': source_id, 'titulo': info['title'], 'source_url': info['url'], 'catalog_url': info['catalog_url'],
                    'coletado_em': datetime.now(timezone.utc).isoformat(), 'sha256': digest, 'bytes': len(raw),
                    'status': 'extraido' if docs else 'sem_exemplos', 'revisao_humana': 'pendente',
                    'jurisdicao': info.get('jurisdicao', 'nacional'), 'natureza': 'exemplo_oficial_municipal' if info['example'] else 'pacote_schema_sem_instancias',
                    'originais': [{'arquivo': (folder / 'original.zip').resolve().as_posix(), 'source_url': info['url'], 'sha256': digest, 'bytes': len(raw)}],
                    'arquivos_xml': len(docs), 'documentos': docs}
            _write_atomic(metadata_path, json.dumps(meta, ensure_ascii=False, indent=2))
            lines = [f'# {info["title"]}', '', f'Fonte: {info["url"]}', '', f'Estado: {meta["status"]}. XMLs: {len(docs)}.', '',
                     '> Exemplos de integração; assinatura, autorização e validade fiscal não verificadas. SP não cobre DF nem padrão nacional.', '']
            for doc in docs:
                lines += [f'## {doc["nome_no_pacote"]}', '', f'Raiz: {doc["raiz"]}; modelo: {doc["modelo"]}; ambiente: {doc["ambiente"]}; versões internas: {doc["versoes_internas"]}.', '', '| Caminho | Valor |', '|---|---|']
                lines += [f'| {f["caminho"]} | {str(f["valor"] or "").replace(chr(10), " ").replace("|", "&#124;")} |' for f in doc['campos']]
            _write_atomic(folder / 'documento.md', '\n'.join(lines) + '\n')
            results.append(meta)
        except (httpx.HTTPError, ValueError, OSError) as exc:
            results.append({'source_id': source_id, 'source_url': info['url'], 'status': 'erro', 'erro': str(exc), 'revisao_humana': 'pendente'})
    report = {'executado_em': datetime.now(timezone.utc).isoformat(), 'total': len(results), 'arquivos_xml': sum(r.get('arquivos_xml', 0) for r in results),
              'falhas': sum(r['status'] == 'erro' for r in results), 'fontes_descoberta': DISCOVERY,
              'lacunas': ['NF-e modelo 55', 'NFC-e modelo 65', 'DPS/NFSe nacional', 'eventos nacionais', 'NFS-e DF'], 'documentos': results}
    _write_atomic(output / 'manifesto.json', json.dumps(report, ensure_ascii=False, indent=2))
    lines = ['# XMLs oficiais de exemplo', '', '> Cobertura municipal SP apenas. Não são notas para emissão nem prova de homologação. Sem dados privados coletados de consultas fiscais.', '',
             f'Pacotes inspecionados: {len(results)}; XMLs: {report["arquivos_xml"]}; falhas: {report["falhas"]}.', '', '| Fonte | Estado | XMLs |', '|---|---|---|']
    for result in results:
        lines.append(f'| [{result["source_id"]}]({result["source_url"]}) | {result["status"]} | {result.get("arquivos_xml", 0)} |')
    lines += ['', '## Lacunas', '', *[f'- {gap}' for gap in report['lacunas']], '', '## Descoberta', '']
    lines += [f'- [{s["escopo"]}]({s["source_url"]}): {s["resultado"]}' for s in DISCOVERY]
    _write_atomic(output / 'indice.md', '\n'.join(lines) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=[*SOURCES, 'all'], default='all')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    with httpx.Client(timeout=90, follow_redirects=True, headers={'User-Agent': 'SocioDigital-Crawler/0.1'}) as client:
        report = collect(list(SOURCES) if args.source == 'all' else [args.source], args.output, client)
    print(f'XMLs: {report["arquivos_xml"]}; falhas: {report["falhas"]}; índice: {args.output.resolve() / "indice.md"}')
    return int(report['falhas'] > 0)


if __name__ == '__main__':
    raise SystemExit(main())
