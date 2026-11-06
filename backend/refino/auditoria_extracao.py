"""Auditoria de extração e duplicatas físicas: relata problemas e nunca altera originais, índice ou arquivos.

Problemas de ocorrência vão para fila_revisao.jsonl; a ocorrência continua no índice.
"""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import threading

from bs4 import BeautifulSoup
import pypdfium2 as pdfium

from backend.crawler.catalogo import Hasher, frontmatter
from backend.refino.pipeline import load_policy, normalize_text

_FECHA_BODY = re.compile(rb'</body\s*>', re.I)
_HTML = ('.html', '.htm')
_CONVERSIVEIS = ('.doc', '.docx', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')  # formatos que backend.crawler.recuperar_anexos converte
_OUTROS_ANEXOS = ('.rtf', '.odt', '.xls', '.zip')  # sem conversor local: ficam na fila


def carregar_limites(path=None):
    return load_policy(path)['auditoria_extracao']


def _colapsa(texto):
    return ' '.join(texto.split())


def _alnum(texto):
    return re.sub(r'[\W_]+', '', texto.lower())


def _metadados(root, ref):
    try:
        raw = (root / ref).read_bytes()
    except OSError:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return frontmatter(raw.decode('utf-8-sig')) or {}


def _resolver(declarado, root):
    """Arquivo declarado. Caminho herdado ausente é remapeado pelo trecho após a pasta 'data' da raiz."""
    texto = str(declarado or '')
    if not texto:
        return None, False
    p = Path(texto)
    if not p.is_absolute() and (root / p).is_file():
        return root / p, False
    if p.is_absolute() and p.is_file():
        return p, False
    partes = [x for x in re.split(r'[\\/]+', texto) if x]
    if 'data' in partes:
        i = len(partes) - 1 - partes[::-1].index('data')
        rel = partes[i + 1:]
        if rel:
            candidato = root.joinpath(*rel)
            if candidato.is_file() and candidato.resolve().is_relative_to(root.resolve()):
                return candidato, True
    return None, False


_PDFIUM = threading.Lock()  # pdfium não é thread-safe: leituras paralelas falham ou derrubam o processo


def _ler_pdf(path):
    with _PDFIUM:
        return _ler_pdf_serial(path)


def _ler_pdf_serial(path):
    doc = pdfium.PdfDocument(str(path))
    try:
        textos = []
        for i in range(len(doc)):
            pagina = doc[i]
            try:
                tp = pagina.get_textpage()
                try:
                    textos.append(tp.get_text_range().strip())
                finally:
                    tp.close()
            finally:
                pagina.close()
    finally:
        doc.close()
    return len(textos), sum(1 for t in textos if not t), ' '.join(textos)


def auditar(ocorrencia, root, limites=None, hasher=None):
    """Sinais de extração de uma ocorrência. Original ausente vira problema, nunca exceção."""
    root = Path(root)
    limites = limites or carregar_limites()
    hasher = hasher or Hasher()
    problemas = set()
    meta = _metadados(root, ocorrencia['metadados_ref'])
    base = Path(ocorrencia['metadados_ref']).parent
    nome = str(meta.get('original') or '')
    originais = ocorrencia.get('originais') or []
    pares = [(i['arquivo'], i.get('sha256')) for i in originais if i.get('arquivo')]
    if not pares:  # hash sem caminho, como no refino: nome declarado nos metadados ou convenção original.html
        sha_meta = next((i['sha256'] for i in originais if i.get('sha256')), meta.get('sha256'))
        if nome or (root / base / 'original.html').is_file():
            pares = [(str(base / (nome or 'original.html')), sha_meta)]
    achados = []
    for declarado, sha in pares:
        path, _ = _resolver(declarado, root)
        if path is None:
            problemas.add('original_ausente')
            continue
        if sha and hasher.digest(path) != sha:
            problemas.add('original_divergente')
        achados.append(path)
    html = next((p for p in achados if p.suffix.lower() in _HTML), None)
    pdf = next((p for p in achados if p.suffix.lower() == '.pdf'), None)
    md = None
    if ocorrencia.get('markdown_ref') and (root / ocorrencia['markdown_ref']).is_file():
        md = normalize_text((root / ocorrencia['markdown_ref']).read_bytes().decode('utf-8-sig'))
    resultado = dict(paginas=None, paginas_sem_texto=None, razao_texto=None, bytes_apos_body=None,
                     original_ref=None, markdown_ref=ocorrencia.get('markdown_ref'), recuperavel=False)
    visivel = None
    if html is not None:
        resultado['original_ref'] = html.relative_to(root).as_posix() if html.is_relative_to(root) else str(html)
        raw = html.read_bytes()
        fecha = _FECHA_BODY.search(raw)
        if fecha:
            resultado['bytes_apos_body'] = len(raw) - fecha.end()
            if resultado['bytes_apos_body'] > limites['bytes_apos_body_precoce']:
                problemas.add('body_precoce')
        soup = BeautifulSoup(raw, 'html.parser')
        for node in soup(['script', 'style', 'head']):
            node.decompose()
        visivel = _colapsa(soup.get_text())
        # Tabela de layout vira texto no Markdown: perdida = início do texto da tabela ausente do Markdown (alfanumérico).
        trechos = [t for t in (_alnum(x.get_text())[:40] for x in soup.find_all('table')) if t]
        if trechos:
            tab_json = (root / ocorrencia['metadados_ref']).parent / 'tabelas.json'
            literais = len(json.loads(tab_json.read_bytes())) if tab_json.is_file() else 0
            md_alnum = _alnum(md or '')
            if sum(1 for t in trechos if t not in md_alnum) > literais:
                problemas.add('tabelas_perdidas')
    if pdf is not None:
        try:
            paginas, sem_texto, texto_pdf = _ler_pdf(pdf)
        except Exception:
            problemas.add('original_ilegivel')
        else:
            resultado.update(paginas=paginas, paginas_sem_texto=sem_texto)
            if paginas and sem_texto == paginas:
                problemas.add('pdf_sem_camada_de_texto')
            elif sem_texto:
                problemas.add('paginas_vazias')
            resultado['original_ref'] = resultado['original_ref'] or (pdf.relative_to(root).as_posix() if pdf.is_relative_to(root) else str(pdf))
            if html is None:
                visivel = _colapsa(texto_pdf)
    if md and visivel:
        resultado['razao_texto'] = round(len(_colapsa(md)) / len(visivel), 4)
        if resultado['razao_texto'] < limites['razao_texto_minima']:
            problemas.add('extracao_curta')
    anexos = [p for p in achados if p.suffix.lower() in _CONVERSIVEIS + _OUTROS_ANEXOS]
    if anexos and md is None:
        problemas.add('anexo_sem_conversao')
        resultado['recuperavel'] = all(p.suffix.lower() in _CONVERSIVEIS for p in anexos)
    resultado['problemas'] = sorted(problemas)
    return resultado


def auditar_lote(ocorrencias, root, limites, workers=8):
    """Linhas só das ocorrências com problema. Lê hash-cache.json da raiz, sem gravá-lo."""
    root = Path(root)
    cache_path = root / 'catalogo' / 'hash-cache.json'
    hasher = Hasher(json.loads(cache_path.read_bytes()) if cache_path.is_file() else {})
    ocorrencias = list(ocorrencias)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        resultados = list(pool.map(lambda o: auditar(o, root, limites, hasher), ocorrencias))
    return [dict(id=o['id'], documento_id=o['documento_id'], frente=o.get('frente'), metadados_ref=o['metadados_ref'], **r)
            for o, r in zip(ocorrencias, resultados) if r['problemas']]


def duplicatas_fisicas(ocorrencias):
    """Mesmo original (hash bruto já registrado) em mais de uma ocorrência. Só lê dicionários."""
    grupos = defaultdict(list)
    for o in ocorrencias:
        if o.get('classificacao') == 'dados_estruturados':  # dados e CNPJ ficam fora da comparação
            continue
        for h in o.get('hashes_originais') or []:
            grupos[h].append(o)
    for h in sorted(grupos):
        ids = sorted({o['id'] for o in grupos[h]})
        if len(ids) > 1:
            yield dict(hash_original=h, ocorrencias=ids, documentos=sorted({o['documento_id'] for o in grupos[h]}))
