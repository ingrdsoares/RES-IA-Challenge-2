"""Auditoria de extração e duplicatas físicas: relata problemas e nunca altera originais, índice ou arquivos.

Só problemas que não são extracao_curta entram em fila_revisao.jsonl; a ocorrência continua no índice.
"""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import threading
import unicodedata
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import pypdfium2 as pdfium

from backend.crawler.catalogo import Hasher, frontmatter
from backend.refino.pipeline import load_policy, normalize_text

_FECHA_BODY = re.compile(rb'</body\s*>', re.I)
_HTML = ('.html', '.htm')
_CONVERSIVEIS = ('.doc', '.docx', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')  # formatos que backend.crawler.recuperar_anexos converte
_OUTROS_ANEXOS = ('.rtf', '.odt', '.xls', '.zip')  # sem conversor local: ficam na fila
_REMOVER_TAGS = ('script', 'style', 'head', 'nav', 'header', 'footer')
_CLASSE_CHROME = re.compile(r'^(nav|navbar|menu|footer|header)(-|$)|-(nav|menu|footer|header)$')  # navegação, cabeçalho, rodapé e menu; não "default-header-template"
_SEGMENTO_MINIMO = 20  # caracteres alfanuméricos de um segmento Receita
_CELULA_MINIMA = 4  # células curtas demais (ex.: "5") não provam nem negam presença
_CURTA_SEM_FILA = 'extracao_curta'  # aparece em auditoria_extracao.jsonl e no manifesto, nunca na fila


def carregar_limites(path=None):
    return load_policy(path)['auditoria_extracao']


def _colapsa(texto):
    return ' '.join(texto.split())


def _sem_destino_de_link(texto):
    """Markdown [texto](url) -> [texto]: a URL não é conteúdo do original."""
    return re.sub(r'\]\([^)]*\)', ']', texto)


def _alnum(texto):
    """Chave comparável: minúsculas, sem pontuação; cada caractere não ASCII vira '?' (acento ou � do original)."""
    decomposto = unicodedata.normalize('NFD', texto.lower())
    sem_marcas = ''.join(c for c in decomposto if unicodedata.category(c) != 'Mn')  # í (NFC ou NFD) vira i
    return re.sub(r'[^a-z0-9?]', '', ''.join('' if c.isspace() else '?' if ord(c) > 127 else c for c in sem_marcas))


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


def _sem_chrome(soup):
    """Tira scripts, estilos e navegação, cabeçalho, rodapé e menus: não são conteúdo da norma."""
    def alvo(tag):
        if tag.name in ('html', 'body'):  # contêineres do documento nunca são cabeçalho ou menu
            return False
        return tag.name in _REMOVER_TAGS or any(_CLASSE_CHROME.search(c) for c in (tag.get('class') or []))
    for node in soup.find_all(alvo):
        if not getattr(node, 'decomposed', False):
            node.decompose()


def _contem(chave, md_alnum):
    """Presença de uma chave; '?' da chave (caractere substituto do original) casa qualquer caractere."""
    if '?' not in chave:
        return chave in md_alnum
    return re.search(re.escape(chave).replace(r'\?', '.'), md_alnum) is not None


def _tabelas_perdidas(soup, md_alnum):
    """Tabela com conteúdo real é perdida se menos de 80% das suas células aparecem no Markdown.

    Tabela de valores nulos (widget do DOU, ex.: "null null null") é ignorada.
    """
    perdidas = 0
    for t in soup.find_all('table'):
        celulas = [c.get_text(' ', strip=True) for c in t.find_all(['td', 'th'])]
        celulas = [c for c in celulas if c]
        if not celulas:
            continue
        nulas = [c for c in celulas if set(c.lower().split()) <= {'null'}]
        if len(nulas) * 2 >= len(celulas):
            continue
        chaves = [k for k in (_alnum(c) for c in celulas if c not in nulas) if len(k) >= _CELULA_MINIMA]
        if chaves and sum(1 for k in chaves if _contem(k, md_alnum)) / len(chaves) < 0.8:
            perdidas += 1
    return perdidas


def _eh_receita(ocorrencia, meta):
    url = str(ocorrencia.get('source_url') or meta.get('source_url') or meta.get('url') or '')
    return (urlsplit(url).hostname or '').lower().endswith('receita.fazenda.gov.br')


def _segmentos_receita(path):
    """Textos integrais (ementas e outros segmentos) do JSON da Receita, já sem marcação, alfanuméricos."""
    dados = json.loads(path.read_bytes())
    textos = []

    def percorrer(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == 'textoIntegra' and isinstance(v, str):
                    textos.append(v)
                else:
                    percorrer(v)
        elif isinstance(x, list):
            for v in x:
                percorrer(v)
    percorrer(dados)
    segmentos = [_alnum(BeautifulSoup(t, 'html.parser').get_text()) for t in textos]
    return [s for s in segmentos if len(s) >= _SEGMENTO_MINIMO]


def _padrao(frase):
    """Regex da frase em que cada caractere não ASCII casa qualquer caractere (acento ou � do original)."""
    return re.compile(''.join('.' if ord(c) > 127 else (r'\s+' if c.isspace() else re.escape(c)) for c in frase), re.I)


def _depois_do_body(raw, md_alnum, ancora):
    """(bytes após </body>, se o texto desse trecho, antes da cauda de portal, está ausente do Markdown).

    A cauda de portal começa na âncora de politica.json (aviso, formulário de erro, contador, links do DOU) e não conta.
    """
    fecha = _FECHA_BODY.search(raw)
    if not fecha:
        return None, False
    depois = raw[fecha.end():]
    if md_alnum is None:
        return len(depois), False
    sopa = BeautifulSoup(depois, 'html.parser')
    _sem_chrome(sopa)
    texto = sopa.get_text(' ')
    if ancora:
        m = _padrao(ancora).search(texto)
        if m:
            texto = texto[:m.start()]
    trecho = _alnum(texto)
    return len(depois), len(trecho) >= 40 and trecho not in md_alnum


def _presente(segmento, md_alnum):
    """Segmento presente se início e fim aparecem no Markdown (link ou marcação no meio não quebra a presença)."""
    if len(segmento) <= 160:
        return _contem(segmento, md_alnum)
    return _contem(segmento[:80], md_alnum) and _contem(segmento[-80:], md_alnum)


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
    # Original principal é o de metadados['original']; anexos (ex.: HTML de anexo) não são comparados com o Markdown do documento.
    principal = next((p for p in achados if nome and p.name == Path(nome).name), None)
    candidatos = [principal] if principal is not None else achados
    html = next((p for p in candidatos if p.suffix.lower() in _HTML), None)
    pdf = next((p for p in candidatos if p.suffix.lower() == '.pdf'), None)
    json_orig = next((p for p in candidatos if p.suffix.lower() == '.json'), None)
    md = None
    if ocorrencia.get('markdown_ref') and (root / ocorrencia['markdown_ref']).is_file():
        md = normalize_text((root / ocorrencia['markdown_ref']).read_bytes().decode('utf-8-sig'))
    md_alnum = _alnum(_sem_destino_de_link(md)) if md is not None else None
    resultado = dict(paginas=None, paginas_sem_texto=None, razao_texto=None, bytes_apos_body=None,
                     original_ref=None, markdown_ref=ocorrencia.get('markdown_ref'), recuperavel=False, sem_verificacao=False)
    visivel = None
    tem_conteudo = False
    if html is not None:
        resultado['original_ref'] = html.relative_to(root).as_posix() if html.is_relative_to(root) else str(html)
        raw = html.read_bytes()
        tamanho_depois, perdido = _depois_do_body(raw, md_alnum, limites.get('ancora_rodape'))
        if tamanho_depois is not None:
            resultado['bytes_apos_body'] = tamanho_depois
            if tamanho_depois > limites['bytes_apos_body_precoce'] and perdido:
                problemas.add('body_precoce')
        soup = BeautifulSoup(raw, 'html.parser')
        _sem_chrome(soup)
        visivel = _colapsa(soup.get_text())
        tem_conteudo = bool(_alnum(visivel))
        if md_alnum is not None:
            literais = 0
            tab_json = (root / ocorrencia['metadados_ref']).parent / 'tabelas.json'
            if tab_json.is_file():
                try:
                    literais = len(json.loads(tab_json.read_bytes()))
                except (ValueError, TypeError):
                    problemas.add('tabelas_json_corrompido')
            if _tabelas_perdidas(soup, md_alnum) > literais:
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
                tem_conteudo = bool(_alnum(texto_pdf))
    if json_orig is not None:
        if _eh_receita(ocorrencia, meta):
            try:
                segmentos = _segmentos_receita(json_orig)
            except ValueError:
                problemas.add('original_ilegivel')
            else:
                tem_conteudo = tem_conteudo or bool(segmentos)
                if segmentos and md_alnum is not None:
                    if sum(1 for s in segmentos if _presente(s, md_alnum)) / len(segmentos) < 0.95:
                        problemas.add('segmentos_perdidos')
        else:
            resultado['sem_verificacao'] = True
    if md and visivel:
        resultado['razao_texto'] = round(len(_colapsa(md)) / len(visivel), 4)
        if resultado['razao_texto'] < limites['razao_texto_minima']:
            problemas.add('extracao_curta')
    if md is None and tem_conteudo:
        problemas.add('sem_markdown')
    anexos = [p for p in achados if p.suffix.lower() in _CONVERSIVEIS + _OUTROS_ANEXOS]
    if anexos and md is None:
        problemas.add('anexo_sem_conversao')
        resultado['recuperavel'] = all(p.suffix.lower() in _CONVERSIVEIS for p in anexos)
    resultado['problemas'] = sorted(problemas)
    return resultado


def auditar_lote(ocorrencias, root, limites, workers=8):
    """Uma linha por ocorrência, com problemas (vazios quando não há). Lê hash-cache.json da raiz, sem gravá-lo."""
    root = Path(root)
    cache_path = root / 'catalogo' / 'hash-cache.json'
    hasher = Hasher(json.loads(cache_path.read_bytes()) if cache_path.is_file() else {})
    ocorrencias = list(ocorrencias)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        resultados = list(pool.map(lambda o: auditar(o, root, limites, hasher), ocorrencias))
    return [dict(id=o['id'], documento_id=o['documento_id'], frente=o.get('frente'), metadados_ref=o['metadados_ref'], **r)
            for o, r in zip(ocorrencias, resultados)]


def para_fila(linha):
    """Problemas que mandam a ocorrência para fila_revisao (extracao_curta fica só no relatório)."""
    problemas = [p for p in linha['problemas'] if p != _CURTA_SEM_FILA]
    return dict(linha, tipo='auditoria_extracao', problemas=problemas) if problemas else None


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
