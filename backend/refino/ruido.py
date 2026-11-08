"""Limpeza de ruído por lista versionada, sem tocar em conteudos/ nem remover nada por frequência.

Só sai linha inteira que case exatamente com uma regra de ruido.json. Sugestões por frequência
vão para ruido_sugerido.jsonl, para revisão humana; nunca são aplicadas.
"""
from collections import Counter
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
REGRAS = BASE / 'ruido.json'
_LINHA_MAXIMA = 300  # ponytail: sugestão ignora linhas longas (parágrafos); upgrade: sugerir por bloco


def carregar_regras(path=None):
    return json.loads(Path(path or REGRAS).read_bytes())['regras']


def aplicaveis(regras, metadados_indice):
    """Regra com 'exige' só vale se o índice ainda guarda todos esses metadados."""
    return [r for r in regras if set(r.get('exige', ())) <= set(metadados_indice)]


def limpar(texto, regras):
    alvo = {}
    for r in regras:
        alvo.setdefault(r['texto'].strip(), r['id'])
    saida, aplicadas, cortou = [], [], False
    for linha in texto.split('\n'):
        s = linha.strip()
        if s in alvo:
            aplicadas.append(alvo[s])
            cortou = True
            continue
        if not s and cortou and saida and not saida[-1].strip():
            continue
        if s:
            cortou = False
        saida.append(linha)
    return '\n'.join(saida), aplicadas


def sugerir(textos, minimo_textos, saida=None):
    contagem, exemplo = Counter(), {}
    for cid, caminho in textos.items():
        vistos = set()
        for linha in Path(caminho).read_text(encoding='utf8').split('\n'):
            s = linha.strip()
            if s and len(s) <= _LINHA_MAXIMA and s not in vistos:
                vistos.add(s)
                contagem[s] += 1
                exemplo.setdefault(s, cid)
    rows = [dict(texto=s, textos=n, exemplo=exemplo[s], aplicada=False) for s, n in sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0])) if n >= minimo_textos]
    if saida is not None:
        Path(saida).write_bytes(b''.join(json.dumps(r, ensure_ascii=False, sort_keys=True).encode('utf8') + b'\n' for r in rows))
    return rows
