"""Recorte reproduzível de empresas ativas de pequeno porte com estabelecimento no DF."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile
import httpx

from .cnpj import DAV, PUBLIC_AUTH, download, _competence, _member
from .cnpj_ampliado import rows
from .anexos import _cell

DATA = Path(__file__).resolve().parent / 'data'
DEFAULT_OUTPUT = DATA / 'cnpj-df'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sample(establishment, company_files, simples, limit=1000, candidates=20000):
    if not 1 <= limit <= candidates <= 100000:
        raise ValueError('Limites inválidos: 1 <= limit <= candidates <= 100000')
    establishments, companies, options, scanned = {}, {}, {}, {}
    line = 0
    for line, row in rows(Path(establishment), 30):
        if row[5] == '02' and row[19] == 'DF':
            establishments.setdefault(row[0], (line, row))
            if len(establishments) == candidates:
                break
    scanned['estabelecimentos'] = line
    for path in company_files:
        line = 0
        for line, row in rows(Path(path), 7):
            if row[0] in establishments:
                companies.setdefault(row[0], (str(Path(path).resolve()), line, row))
        scanned[Path(path).name] = line
    selected = [root for root in establishments if root in companies and companies[root][2][5] in ('01', '03')][:limit]
    if len(selected) != limit:
        raise ValueError(f'Apenas {len(selected)} empresas DF elegíveis; ampliar candidatos/lotes explicitamente')
    selected_set = set(selected)
    line = 0
    for line, row in rows(Path(simples), 7):
        if row[0] in selected_set:
            options[row[0]] = (line, row)
        if len(options) == limit:
            break
    scanned['simples'] = line
    records = []
    for root in selected:
        el, e = establishments[root]
        source, cl, c = companies[root]
        sl, s = options.get(root, (None, None))
        records.append({'cnpj_basico': root, 'cnpj': ''.join(e[:3]),
            'razao_social': re.sub(r'(?<!\d)(?:\d{11}|\d{3}\.\d{3}\.\d{3}-\d{2})(?!\d)', '[CPF omitido]', c[1]),
            'porte': c[5], 'situacao': e[5], 'uf': e[19], 'municipio': e[20],
            'matriz_filial': e[3], 'cnae_principal': e[11], 'cnaes_secundarios': e[12],
            'registro_simples_encontrado': s is not None,
            **{key: s[i] if s else None for i, key in enumerate(('', 'opcao_simples', 'data_opcao_simples', 'data_exclusao_simples', 'opcao_mei', 'data_opcao_mei', 'data_exclusao_mei')) if i},
            'linhas_origem': {'estabelecimentos': el, 'empresas': cl, 'simples': sl},
            'arquivo_empresas': source})
    return records, {'linhas_escaneadas': scanned, 'candidatos_df_ativos': len(establishments),
        'candidatos_com_empresa': len(companies), 'candidatos_sem_empresa': len(establishments)-len(companies),
        'elegiveis_nos_candidatos': sum(c[2][5] in ('01','03') for c in companies.values()),
        'sem_registro_simples': len(selected)-len(options)}



def publish_index(output, competencia, identity, meta):
    base = Path(output)/competencia
    manifest = {'source_id': 'cnpj_df', 'competencia': competencia, 'snapshot': identity,
                'registros': meta['registros'], 'cobertura': meta['cobertura']}
    (base/'manifesto.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    Path(output,'indice.md').write_text(f"# CNPJ DF\n\n[{meta['registros']} raízes ativas DF]({competencia}/{identity}/dados.md) · [Metadados]({competencia}/{identity}/metadados.json)\n", encoding='utf-8')


def collect(output=DEFAULT_OUTPUT, competencia='2026-10', limit=1000, candidates=20000):
    competencia = _competence(competencia)
    raw = DATA / 'cnpj-ampliado' / competencia / 'raw'
    sources = [(raw/'Estabelecimentos1.zip', 'Estabelecimentos1.zip'),
               (raw/'Empresas2.zip', 'Empresas2.zip'), (raw/'Simples.zip', 'Simples.zip')]
    cached_company = DATA/'inspection'/'Empresas1-2026-10.zip'
    if competencia != '2026-10' or not cached_company.exists():
        cached_company = raw/'Empresas1.zip'
    sources.append((cached_company, 'Empresas1.zip'))
    with httpx.Client(auth=PUBLIC_AUTH, timeout=120, follow_redirects=True) as client:
        for path, name in sources:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.part')
                download(client, DAV+competencia+'/'+name, temporary, max_bytes=700*1024**2)
                temporary.replace(path)
    originals = []
    for path, name in sources:
        with zipfile.ZipFile(path) as archive:
            _member(archive, 8*1024**3)
        originals.append({'arquivo': str(path.resolve()), 'source_url': DAV+competencia+'/'+name,
                          'sha256': digest(path), 'bytes': path.stat().st_size})
    identity_data = {'competencia': competencia, 'uf': 'DF', 'situacao': '02', 'portes': ['01','03'],
        'limit': limit, 'candidates': candidates, 'fontes': originals, 'versao': 1}
    identity = hashlib.sha256(json.dumps(identity_data, sort_keys=True).encode()).hexdigest()
    base = Path(output)/competencia
    target = base/identity
    if (target/'metadados.json').exists():
        meta = json.loads((target/'metadados.json').read_text(encoding='utf-8'))
        for name, checksum in meta['artefatos_sha256'].items():
            if digest(target/name) != checksum:
                raise ValueError(f'Cache corrompido: {target/name}; original preservado')
        publish_index(output, competencia, identity, meta)
        return target
    records, coverage = sample(sources[0][0], [p for p, n in sources if n.startswith('Empresas')], sources[2][0], limit, candidates)
    target.mkdir(parents=True, exist_ok=True)
    methodology = (f'Primeiras {candidates} raízes distintas com estabelecimento ativo (02) no DF no lote Estabelecimentos1; '
        f"cruzamento com {', '.join(n for _, n in sources if n.startswith('Empresas'))}, portes 01/03; primeiras {limit} elegíveis na ordem dos estabelecimentos. "
        'Uma linha por raiz; filiais adicionais descartadas. Amostra de conveniência, sem representatividade estatística; não é censo do DF. '
        'Ausência no arquivo Simples não significa opção N. Opções e datas preservadas literalmente. '
        'Endereços, contatos, CPF e QSA não integram os dados derivados. Originais integrais permanecem locais e são referenciados sem cópia.')
    text = '# CNPJ — recorte DF\n\n'+methodology+'\n\nCompetência: '+competencia+'\n\n| CNPJ | Razão social | Porte | UF | CNAE | Simples | MEI |\n|---|---|---|---|---|---|---|\n'
    for r in records:
        text += '| '+' | '.join(_cell(str(r[k] if r[k] is not None else 'não encontrado')) for k in ('cnpj','razao_social','porte','uf','cnae_principal','opcao_simples','opcao_mei'))+' |\n'
    (target/'dados.md').write_text(text, encoding='utf-8')
    (target/'registros.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    meta = {'source_id': 'cnpj_df', 'source_url': DAV+competencia+'/', 'coletado_em': datetime.now(timezone.utc).isoformat(),
        'sha256': identity, 'competencia': competencia, 'originais': originals, 'registros': len(records),
        'status': 'extraido', 'revisao_humana': 'pendente', 'amostragem': methodology, 'filtros': identity_data,
        'cobertura': coverage, 'artefatos_sha256': {name: digest(target/name) for name in ('dados.md','registros.json')}}
    (target/'metadados.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    publish_index(output, competencia, identity, meta)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--competencia', default='2026-10')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--candidates', type=int, default=20000)
    args = parser.parse_args()
    print(collect(competencia=args.competencia, limit=args.limit, candidates=args.candidates))
