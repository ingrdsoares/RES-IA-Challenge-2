"""Auditoria de extração por sinais do original HTML; só relata, nunca exclui nada do índice.

extracao_curta: Markdown muito menor que o texto visível do HTML original (razão em politica.json).
body_precoce: </body> seguido de muito conteúdo, sinal do caso em que um conversor leu só soup.body.
"""
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from backend.refino.pipeline import load_policy, normalize_text

_FECHA_BODY = re.compile(rb'</body\s*>', re.I)


def carregar_limites(path=None):
    return load_policy(path)['auditoria_extracao']


def _colapsa(texto):
    return ' '.join(texto.split())


def _original_html(root, metadados_ref):
    """Original HTML ao lado dos metadados; nome legado (caminho absoluto) vira só o nome do arquivo."""
    meta_path = root / metadados_ref
    pasta = meta_path.parent
    try:
        nome = json.loads(meta_path.read_bytes()).get('original') or 'original.html'
    except (OSError, ValueError, AttributeError):
        nome = 'original.html'
    nome = Path(str(nome).replace('\\', '/')).name
    if not nome.lower().endswith(('.html', '.htm')):
        return None
    candidato = pasta / nome
    return candidato if candidato.is_file() else None


def auditar(ocorrencia, root, limites):
    """Sinais de extração de uma ocorrência; ausência de original HTML não gera problema."""
    root = Path(root)
    resultado = {'problemas': [], 'razao_texto': None, 'bytes_apos_body': None, 'original_ref': None, 'markdown_ref': ocorrencia.get('markdown_ref')}
    original = _original_html(root, ocorrencia['metadados_ref'])
    if original is None:
        return resultado
    raw = original.read_bytes()
    resultado['original_ref'] = original.relative_to(root).as_posix()
    fecha = _FECHA_BODY.search(raw)
    if fecha:
        resultado['bytes_apos_body'] = len(raw) - fecha.end()
        if resultado['bytes_apos_body'] > limites['bytes_apos_body_precoce']:
            resultado['problemas'].append('body_precoce')
    if ocorrencia.get('markdown_ref'):
        visivel = _colapsa(BeautifulSoup(raw, 'html.parser').get_text())
        markdown = _colapsa(normalize_text((root / ocorrencia['markdown_ref']).read_bytes().decode('utf-8-sig')))
        if visivel:
            resultado['razao_texto'] = round(len(markdown) / len(visivel), 4)
            if resultado['razao_texto'] < limites['razao_texto_minima']:
                resultado['problemas'].insert(0, 'extracao_curta')
    return resultado


def auditar_ocorrencias(ocorrencias, root, limites):
    """Linhas de auditoria só para ocorrências com problema; a entrada não é alterada."""
    for occ in ocorrencias:
        resultado = auditar(occ, root, limites)
        if resultado['problemas']:
            yield dict(id=occ['id'], **resultado)
