"""Similaridade como alarme: pares candidatos entre conteúdos únicos.

Não funde documentos, não altera índice e não remove nada da busca; só produz relatório.
"""
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from pathlib import Path
import json
import re
import unicodedata
import zlib

import numpy as np

SUSPEITAS = ('so_formatacao', 'reordenado', 'so_numeros', 'poucas_palavras')
PARAMS = json.loads((Path(__file__).resolve().parent / 'politica.json').read_bytes())['similaridade']
BUCKET_MAX = 50  # ponytail: bucket maior que isso vira estrela + vizinhos; pode perder pares dentro dele, upgrade: bucket por sub-hash
_TOKEN = re.compile(r'\d+(?:[.,/\-]\d+)*|[a-z]+')
_COMBINANTE = re.compile(r'[̀-ͯ]')
_MISTURA = np.uint64(0xff51afd7ed558ccd)
_BASE = 1099511628211
_DESLOC = np.uint64(33)


@dataclass(frozen=True)
class Par:
    a: str
    b: str
    jaccard: float
    classe: str
    relacao: str
    n_dif: int
    tokens_dif: tuple


def tokens(texto):
    return _TOKEN.findall(_COMBINANTE.sub('', unicodedata.normalize('NFD', texto).lower()))


def _assinatura(toks, params):
    k = params['shingles']
    if len(toks) < k + 25:  # ponytail: texto curto fica fora do LSH (não é comparado), sem erro
        return None, None
    h = np.array([zlib.crc32(t.encode()) for t in toks], dtype=np.uint64)
    pesos = np.array([pow(_BASE, i, 2**64) for i in range(k)], dtype=np.uint64)
    x = (np.lib.stride_tricks.sliding_window_view(h, k) * pesos).sum(axis=1, dtype=np.uint64)
    x ^= x >> _DESLOC
    x *= _MISTURA
    x ^= x >> _DESLOC
    shingles = np.unique(x)
    rng = np.random.default_rng(42)
    perms = params['permutacoes']
    a = rng.integers(1, 2**63, perms, dtype=np.uint64) | np.uint64(1)
    b = rng.integers(1, 2**63, perms, dtype=np.uint64)
    sig = np.array([((ai * shingles + bi) >> np.uint64(32)).min() for ai, bi in zip(a, b)], dtype=np.uint64)
    return shingles, sig


def _extrair(job):
    cid, caminho, params = job
    shingles, sig = _assinatura(tokens(Path(caminho).read_text('utf-8', 'replace')), params)
    return cid, shingles, sig


def _candidatos(sigs, params):
    linhas = params['permutacoes'] // params['bandas']
    buckets = defaultdict(list)
    for cid in sorted(sigs):
        for banda in range(params['bandas']):
            buckets[(banda, sigs[cid][banda * linhas:(banda + 1) * linhas].tobytes())].append(cid)
    pares = set()
    for membros in buckets.values():
        if len(membros) < 2:
            continue
        if len(membros) <= BUCKET_MAX:
            pares.update(combinations(membros, 2))
        else:
            pares.update((membros[0], x) for x in membros[1:])
            pares.update(zip(membros, membros[1:]))
    return pares


def _classificar(ta, tb):
    if ta == tb:
        return 'so_formatacao', 0, ()
    ca, cb = Counter(ta), Counter(tb)
    if ca == cb:
        return 'reordenado', 0, ()
    diff = list(((ca - cb) + (cb - ca)).elements())
    amostra = tuple(w for w, _ in Counter(diff).most_common(12))
    if all(any(c.isdigit() for c in w) for w in diff):
        return 'so_numeros', len(diff), amostra
    pequena = len(diff) <= 0.01 * max(len(ta), len(tb))
    return ('poucas_palavras' if pequena else 'texto_diferente'), len(diff), amostra


def comparar(textos, workers=8, documentos=None, params=None):
    """textos: conteudo_id -> arquivo. documentos: conteudo_id -> ids de documento que o contêm (sem isso, tudo é documentos_diferentes)."""
    params = params or PARAMS
    if not 1 <= workers <= 16:
        raise ValueError('Concorrência local deve estar entre 1 e 16')
    jobs = [(cid, str(textos[cid]), params) for cid in sorted(textos)]
    if workers == 1:
        extraidos = [_extrair(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            extraidos = list(pool.map(_extrair, jobs, chunksize=16))
    shingles = {cid: sh for cid, sh, _ in extraidos if sh is not None}
    sigs = {cid: sg for cid, _, sg in extraidos if sg is not None}
    limiar = params['limiar_jaccard']

    @lru_cache(maxsize=256)
    def toks(cid):
        return tokens(Path(textos[cid]).read_text('utf-8', 'replace'))

    pares = []
    for a, b in sorted(_candidatos(sigs, params)):
        sa, sb = shingles[a], shingles[b]
        if min(len(sa), len(sb)) / max(len(sa), len(sb)) < limiar:
            continue
        inter = np.intersect1d(sa, sb, assume_unique=True).size
        jaccard = inter / (len(sa) + len(sb) - inter)
        if jaccard < limiar:
            continue
        classe, n_dif, amostra = _classificar(toks(a), toks(b))
        mesmo = documentos is not None and bool(documentos.get(a, set()) & documentos.get(b, set()))
        pares.append(Par(a, b, round(float(jaccard), 4), classe, 'mesmo_documento' if mesmo else 'documentos_diferentes', n_dif, amostra))
    return pares


def suspeitos(pares):
    return [p for p in pares if p.relacao == 'documentos_diferentes' and p.classe in SUSPEITAS]
