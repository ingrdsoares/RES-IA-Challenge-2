"""Inventario de normas: o que o acervo cita versus o que ja tem. Alimenta a coleta guiada por citacoes."""
import argparse
import json
import re
from dataclasses import asdict, replace
from multiprocessing import Pool
from pathlib import Path

from backend.crawler.citacoes import extrair_citacoes
from backend.crawler.normas_id import NormaId, _sem_acento, identidade_titulo

DESTINO_PADRAO = Path(__file__).parent / 'data' / 'normas-citadas' / 'inventario'
SEMENTES_PADRAO = Path(__file__).parent / 'normas_sementes.json'
FRENTES_DF = {'distrital-df', 'icms-consultas-df', 'consultas-df-amplas'}
NAO_NORMA = {'consulta_tributaria', 'interpretacao_administrativa', 'jurisprudencia_tarf', 'anexo_convertido'}
_EXEMPLOS = 3


def _jur(frente: str) -> str:
    return 'df' if frente in FRENTES_DF else 'federal'


def _extrair(arg):
    """Worker de topo (Windows): (caminho, jur_origem) -> citacoes serializaveis."""
    caminho, jur = arg
    try:
        texto = Path(caminho).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    return [(c.norma.tipo, c.norma.numero, c.norma.ano, c.norma.orgao, c.trecho, c.candidatas_jurisdicao)
            for c in extrair_citacoes(texto, jur)]


def _continua(tipo: str, numero: int) -> bool:
    """Numeracao continua entre anos: o numero identifica a norma mesmo sem ano."""
    return tipo in ('lei', 'lc', 'ec', 'dl') or (tipo == 'decreto' and numero >= 1000)


def _casa(coletada: NormaId, n: NormaId, jurs) -> bool:
    """Coletada sem ano/orgao e curinga; citada sem ano so em numeracao continua; orgao None da citada e curinga."""
    return (coletada.tipo == n.tipo and coletada.numero == n.numero and coletada.jurisdicao in jurs
            and (coletada.ano is None or coletada.ano == n.ano or (n.ano is None and _continua(n.tipo, n.numero)))
            and (coletada.orgao is None or n.orgao is None or coletada.orgao == n.orgao))


def _chave(n: NormaId, assunto: str | None = None) -> str:
    return n.chave + (f'#{assunto.lower()}' if assunto else '')


def _linha(n, docs, exemplos, origem, ligacao, assunto=None, ordem=None):
    return {**({'candidata_ordem': ordem} if ordem is not None else {}), 'chave': _chave(n, assunto), 'norma': asdict(n), 'docs': set(docs), 'exemplos': list(exemplos),
            'situacao': 'pendente', 'motivo': None, 'origem': origem, 'ligacao': ligacao,
            **({'assunto': assunto} if assunto else {})}


def _somar(a, b):
    a['docs'] |= b['docs']
    a['exemplos'] = (a['exemplos'] + [e for e in b['exemplos'] if e not in a['exemplos']])[:_EXEMPLOS]
    if b['ligacao'] == 'certa':
        a['ligacao'] = 'certa'
        a.pop('candidata_ordem', None)
    if b['origem'] == 'semente':
        a['origem'] = 'semente'


def _ano_dominante(linhas: dict):
    """Numeracao continua: ano com 3x as citacoes de cada outro (ou unico) domina; minoritarios viram ambigua."""
    grupos: dict = {}
    for l in linhas.values():
        n = l['norma']
        if l['origem'] == 'citacao' and n['ano'] is not None and _continua(n['tipo'], n['numero']):
            grupos.setdefault((n['tipo'], n['numero'], n['jurisdicao'], n['orgao']), []).append(l)
    for g in grupos.values():
        top = max(g, key=lambda x: len(x['docs']))
        if any(len(o['docs']) * 3 > len(top['docs']) for o in g if o is not top):
            continue
        n = top['norma']
        for o in g:
            if o is not top and o['situacao'] == 'pendente':
                o['situacao'] = 'ambigua'
                o['motivo'] = f"ano divergente do dominante {n['ano']}"
        for k, l in list(linhas.items()):
            m = l['norma']
            if (l['origem'] == 'citacao' and l['situacao'] == 'pendente' and m['ano'] is None
                    and (m['tipo'], m['numero'], m['jurisdicao'], m['orgao']) == (n['tipo'], n['numero'], n['jurisdicao'], n['orgao'])):
                _somar(top, l)
                del linhas[k]


def _dobrar_gemeas(linhas: dict):
    """Linha de dois candidatos com irma 'certa' na outra jurisdicao (mesmo tipo/numero/ano/orgao) some nela."""
    for k, l in list(linhas.items()):
        if l['ligacao'] != 'ambigua' or l['origem'] != 'citacao':
            continue
        n = l['norma']
        outra = [i for i in linhas.values() if i['ligacao'] == 'certa' and i['norma']['jurisdicao'] != n['jurisdicao']
                 and all(i['norma'][f] == n[f] for f in ('tipo', 'numero', 'ano', 'orgao'))]
        if outra:
            _somar(outra[0], l)
            del linhas[k]


def _juntar_irmas(linhas: dict, campo: str):
    """Linha com `campo` (ano/orgao) None: 1 irma com valor -> funde; varias -> ambigua."""
    for k, l in list(linhas.items()):
        n = l['norma']
        if k not in linhas or l['situacao'] != 'pendente' or n[campo] is not None or n['tipo'] == 'assunto':
            continue
        outro = 'orgao' if campo == 'ano' else 'ano'
        irmas = [i for i in linhas.values() if i is not l and i['situacao'] == 'pendente' and i['origem'] == 'citacao'
                 and all(i['norma'][f] == n[f] for f in ('tipo', 'numero', 'jurisdicao', outro))
                 and i['norma'][campo] is not None]
        if len(irmas) == 1:
            _somar(irmas[0], l)
            del linhas[k]
        elif irmas:
            l['situacao'] = 'ambigua'
            l['motivo'] = f"{campo} nao informado na citacao; candidatos: " + ', '.join(sorted(str(i['norma'][campo]) for i in irmas))


def inventariar(run_dir: Path, sementes: Path = SEMENTES_PADRAO, destino: Path = DESTINO_PADRAO,
                processos: int | None = None) -> dict:
    run_dir, destino = Path(run_dir), Path(destino)
    ocs = [json.loads(l) for l in (run_dir / 'ocorrencias.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    # normas coletadas (interpretacoes, consultas etc. nao contam)
    coletadas, titulos = [], []
    for o in ocs:
        if o.get('natureza') in NAO_NORMA:
            continue
        titulos.append(_sem_acento(o.get('titulo') or ''))
        n = identidade_titulo(o.get('titulo') or '', _jur(o.get('frente', '')))
        if n:
            coletadas.append(n)
    # citacoes: extrai por (conteudo, jurisdicao de origem); conta por documento
    citantes = [o for o in ocs if o.get('conteudo_id')]  # ocorrencia com erro nao tem conteudo
    tarefas = sorted({(o['conteudo_id'], _jur(o.get('frente', ''))) for o in citantes})
    args = [(str(run_dir / 'conteudos' / f'{c}.md'), j) for c, j in tarefas]
    if processos == 1 or len(args) < 200:
        res = list(map(_extrair, args))
    else:
        with Pool(processos) as p:
            res = p.map(_extrair, args, chunksize=50)
    por_tarefa = dict(zip(tarefas, res))
    grupos: dict = {}  # (tipo, numero, ano, orgao, cands) -> {docs, exemplos}
    for doc, cid, jur in sorted({(o['documento_id'], o['conteudo_id'], _jur(o.get('frente', ''))) for o in citantes}):
        for tipo, num, ano, org, trecho, cands in por_tarefa[(cid, jur)]:
            g = grupos.setdefault((tipo, num, ano, org, cands), {'docs': set(), 'exemplos': []})
            g['docs'].add(doc)
            if len(g['exemplos']) < _EXEMPLOS:
                g['exemplos'].append(trecho)

    linhas: dict = {}

    def entra(l):
        if l['chave'] in linhas:
            _somar(linhas[l['chave']], l)
        else:
            linhas[l['chave']] = l

    def existente(n, jurs):
        return next((c for c in sorted(coletadas, key=lambda c: (c.ano is None, c.jurisdicao != jurs[0]))
                     if _casa(c, n, jurs)), None)

    for (tipo, num, ano, org, cands), g in sorted(grupos.items(), key=lambda kv: repr(kv[0])):
        base = NormaId(tipo, num, ano, cands[0], org)
        c = existente(base, cands)
        if c:
            n = replace(base, jurisdicao=c.jurisdicao, ano=ano or c.ano, orgao=org or c.orgao)
            l = _linha(n, g['docs'], g['exemplos'], 'citacao', 'certa')
            l['situacao'] = 'ja_existia'
            entra(l)
            continue
        lig = 'certa' if len(cands) == 1 else 'ambigua'
        for j in cands:
            entra(_linha(replace(base, jurisdicao=j), g['docs'], g['exemplos'], 'citacao', lig,
                         ordem=cands.index(j) if lig == 'ambigua' else None))

    for s in json.loads(Path(sementes).read_text(encoding='utf-8')):
        n = NormaId(s['tipo'], s['numero'], s.get('ano'), s['jurisdicao'], s.get('orgao'))
        l = _linha(n, set(), [], 'semente', 'certa', s.get('assunto'))
        rx = s.get('titulo_regex')
        if (rx and any(re.search(rx, t) for t in titulos)) or (not rx and not s.get('assunto') and existente(n, (n.jurisdicao,))):
            l['situacao'] = 'ja_existia'
        entra(l)

    # so pendentes participam da fusao de irmas
    _dobrar_gemeas(linhas)
    _juntar_irmas(linhas, 'orgao')
    _ano_dominante(linhas)
    _juntar_irmas(linhas, 'ano')

    saida = []
    for l in sorted(linhas.values(), key=lambda x: (-len(x['docs']), x['chave'])):
        l['citado_em'] = len(l.pop('docs'))
        saida.append(l)
    r = {'run': run_dir.name, 'total': len(saida), 'linhas': saida}
    destino.mkdir(parents=True, exist_ok=True)
    (destino / 'inventario.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    return r


if __name__ == '__main__':
    from collections import Counter
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run_dir', type=Path)
    ap.add_argument('--sementes', type=Path, default=SEMENTES_PADRAO)
    ap.add_argument('--destino', type=Path, default=DESTINO_PADRAO)
    a = ap.parse_args()
    r = inventariar(a.run_dir, a.sementes, a.destino)
    print(r['total'], dict(Counter(x['situacao'] for x in r['linhas'])))

