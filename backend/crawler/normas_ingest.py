"""Validacao de identidade e gravacao das normas citadas (sem rede).

Layout: <destino>/normas-citadas/<chave-segura>/<sha256>/{original.*, documento.md, metadados.json}.
Associar o texto a norma errada invalida a entrega: so grava depois de ler tipo, numero e ano no cabecalho.
"""
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from backend.crawler.anexos import extract_pdf, render_pages
from backend.crawler.fontes_normas import Candidato, Http, decodificar
from backend.crawler.legislacao import _convert
from backend.crawler.normas_id import NormaId, _sem_acento

_JURISDICAO_DA_FONTE = {'sinj': 'df', 'confaz': 'confaz'}  # as demais fontes sao federais
_ROTULOS = [
    ('lc', r'lei\s+complementar'), ('dl', r'decreto[\s-]+lei'), ('mp', r'medida\s+provisoria'),
    ('ec', r'emenda\s+constitucional'), ('lei', r'lei(?:\s+ordinaria)?'), ('decreto', r'decreto'),
    ('portaria', r'portaria(?:\s+(?:normativa|conjunta))?'),
    ('in', r'instrucao\s+normativa(?:\s+conjunta)?'),
    ('ade', r'ato\s+declaratorio(?:\s+executivo)?'), ('resol_cgsn', r'resolucao(?:\s+cgsn)?'),
    ('convenio_icms', r'convenio\s+icms'), ('ajuste_sinief', r'ajuste\s+sinief'),
]
_NOME = {'lc': 'Lei Complementar', 'dl': 'Decreto-Lei', 'mp': 'Medida Provisória', 'ec': 'Emenda Constitucional',
         'lei': 'Lei', 'decreto': 'Decreto', 'portaria': 'Portaria', 'in': 'Instrução Normativa',
         'ade': 'Ato Declaratório Executivo', 'resol_cgsn': 'Resolução', 'convenio_icms': 'Convênio ICMS',
         'ajuste_sinief': 'Ajuste SINIEF'}
# epigrafe = rotulo [orgao] [nº] numero + data ("de 29 de dezembro de 2003", "de 08/11/1996") ou "/2003", "/03"
_EPIGRAFE = re.compile(
    r'\b(?:' + '|'.join(f'(?P<{k}>{p})' for k, p in _ROTULOS) + r')'
    r'\s+(?:(?!no?\b)(?P<orgao>[a-z]{2,6}(?:/[a-z]{2,6})*)\s+)?'
    r'(?:n\s*[º°o.]*\s*)?(?P<num>\d{1,3}(?:\.\d{3})+|\d{1,6})'
    r'(?:\s*,?\s*de\s+(?:\d{1,2}[º°o]?\s+de\s+[a-z]+\s+de\s+(?P<a2>\d{4})|\d{1,2}/\d{1,2}/(?P<a3>\d{4}))'
    r'|\s*/\s*(?P<a1>\d{4}|\d{2})\b)')
_CITADA = re.compile(r'\b(?:a|as|o|os|da|do|das|dos|na|no|nas|nos|pela|pelo|pelas|pelos|ao|aos|com|em|e|ou|que|vide)\s+$')
_DISPOSITIVO = re.compile(r'\bart\.?\s*1\s*[º°o]?(?!\d)|\bclausula\s+primeira')
_LIMITE_CABECALHO = 5000


def identificar_cabecalho(texto: str) -> tuple[str, int, int, str | None] | None:
    """(tipo, numero, ano, orgao) da primeira epigrafe do cabecalho; None se nao houver.

    O cabecalho vai ate o primeiro dispositivo. Epigrafe precedida de preposicao/"Vide" e citacao de outra
    norma ("Altera a Lei nº 9.718, de ...") e e ignorada.
    """
    t = _sem_acento(' '.join(texto.split()))
    corte = _DISPOSITIVO.search(t)
    cab = t[:min(corte.start() if corte else len(t), _LIMITE_CABECALHO)]
    for m in _EPIGRAFE.finditer(cab):
        if _CITADA.search(cab[max(0, m.start() - 12):m.start()]):
            continue
        tipo = next(k for k, _ in _ROTULOS if m.group(k))
        ano = int(m.group('a2') or m.group('a3') or m.group('a1'))
        if ano < 100:
            ano += 2000 if ano < 40 else 1900
        return tipo, int(m.group('num').replace('.', '')), ano, m.group('orgao')
    return None


def validar_identidade(norma: NormaId, texto: str) -> bool:
    achada = identificar_cabecalho(texto)
    if achada is None:
        return False
    tipo, numero, ano, orgao = achada
    if tipo != norma.tipo or numero != norma.numero or (norma.ano is not None and ano != norma.ano):
        return False
    if norma.orgao and orgao:
        esperado = norma.orgao.lower()
        return esperado == orgao or set(esperado.split('/')) <= set(orgao.split('/'))
    return True


def chave_segura(chave: str) -> str:
    """Nome de pasta valido no exFAT/Windows, estavel e sem colisao: qualquer troca de caractere ganha um hash."""
    partes, trocou = [], False
    for p in chave.split(':'):
        limpa = re.sub(r'[^a-z0-9.-]', '-', p.lower()).rstrip('.') or '-'
        trocou = trocou or limpa != p
        partes.append(limpa)
    nome = '_'.join(partes)
    if trocou or len(nome) > 60:
        nome = nome[:50].rstrip('._-') + '_' + hashlib.sha256(chave.encode('utf-8')).hexdigest()[:8]
    return nome


def resolver_assunto(assunto: str, http: Http) -> list[NormaId]:
    """Sementes por assunto (IPTU, ITBI, IPVA, ITCD). Sem fixture que prove busca textual no SINJ (so ha busca
    por tipo, numero e ano), devolve [] sem pedir nada: essas sementes terminam como `manual`."""
    return []


def _charset(raw: bytes) -> str | None:
    m = re.search(rb'charset\s*=\s*["\']?([\w-]+)', raw[:3000], re.I)
    return m[1].decode('ascii') if m else None


def _html(candidato: Candidato, raw: bytes) -> tuple[str, str]:
    soup = BeautifulSoup(decodificar(raw, _charset(raw)), 'html.parser')
    for no in soup(['script', 'style']):
        no.decompose()
    pagina = soup.get_text(' ', strip=True)  # a epigrafe pode estar fora do bloco que vira Markdown (Camara)
    seletores = {'sinj': ['#div_texto'], 'confaz': ['#content-core', '#plone-content'],
                 'camara': ['.textoNorma'], 'lexml': ['.textoNorma']}.get(candidato.fonte, [])
    raiz = next((r for r in (soup.select_one(s) for s in seletores) if r is not None), None) or soup.body or soup
    return pagina, _convert(str(raiz), candidato.url)


def _receita(candidato: Candidato, raw: bytes) -> tuple[str, str]:
    dados = json.loads(raw)
    if not isinstance(dados, dict) or not isinstance(dados.get('epigrafeCompleta'), str):
        raise ValueError('Resposta da Receita sem epigrafe do ato.')
    segmentos = sorted((dados.get('ementas') or []) + (dados.get('outrosSegmentos') or []),
                       key=lambda s: s.get('ordemSegmentoAto', 0))
    if not segmentos:
        raise ValueError('Ato da Receita sem segmentos de texto.')
    linhas = ['## ' + dados['epigrafeCompleta'], '']
    for seg in segmentos:
        marcas = [rotulo for campo, rotulo in (('tachado', 'TACHADO NA FONTE'), ('agendado', 'AGENDADO NA FONTE'),
                                               ('omitir', 'MARCADO PARA OMISSÃO NA FONTE')) if seg.get(campo)]
        if marcas:
            linhas += ['> ' + '; '.join(marcas) + '. Preservado conforme a fonte.', '']
        linhas += [_convert(seg['textoIntegra'], candidato.url), '']
    return dados['epigrafeCompleta'] + ' ' + '\n'.join(linhas), '\n'.join(linhas)


def _lido(candidato: Candidato, raw: bytes) -> tuple[str, str, str | None]:
    """(extensao do original, texto para validar, Markdown ou None quando o PDF nao tem texto)."""
    if raw.startswith(b'%PDF'):
        paginas = extract_pdf(raw)
        if not any(p['texto'].strip() for p in paginas):
            return 'pdf', '', None
        return 'pdf', '\n'.join(p['texto'] for p in paginas), '\n'.join(render_pages(paginas))
    if candidato.fonte == 'receita':
        return ('json', *_receita(candidato, raw))
    return ('html', *_html(candidato, raw))


def _confere_existente(alvo: Path, raw: bytes) -> None:
    try:
        meta = json.loads((alvo / 'metadados.json').read_bytes())
        ok = (meta['sha256'] == hashlib.sha256(raw).hexdigest() and (alvo / meta['original']).read_bytes() == raw
              and (meta['status'] == 'extracao_pendente' or (alvo / meta['markdown_arquivo']).is_file()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError('Versão existente incompleta ou divergente.') from exc
    if not ok:
        raise ValueError('Versão existente incompleta ou divergente.')


def ingerir(norma: NormaId, candidato: Candidato, raw: bytes, destino: Path, *, rodada: int = 1,
            coletado_em: datetime | None = None) -> Path:
    """Valida e grava; devolve a pasta da versao (<chave-segura>/<sha256>). Reexecucao com os mesmos bytes e no-op."""
    jurisdicao = _JURISDICAO_DA_FONTE.get(candidato.fonte, 'federal')
    if jurisdicao != norma.jurisdicao:
        raise ValueError(f'jurisdicao da fonte ({jurisdicao}) difere da norma ({norma.jurisdicao}): {norma.chave}')
    sha = hashlib.sha256(raw).hexdigest()
    pasta = Path(destino) / 'normas-citadas' / chave_segura(norma.chave)
    alvo = pasta / sha
    if alvo.exists():
        _confere_existente(alvo, raw)
        return alvo
    extensao, validar, markdown = _lido(candidato, raw)
    achada = None
    if markdown is not None:
        achada = identificar_cabecalho(validar)
        if not validar_identidade(norma, validar):
            raise ValueError(f'identidade divergente: o texto de {candidato.url} nao e {norma.chave}')
    instante = coletado_em or datetime.now(timezone.utc)
    if instante.tzinfo is None:
        raise ValueError('Data da coleta deve incluir fuso horário.')
    titulo = f'{_NOME[norma.tipo]} nº {norma.numero}' + (f'/{achada[2] if achada else norma.ano}' if (achada or norma.ano) else '')
    meta = {'source_url': candidato.url, 'source_id': f'{candidato.fonte}:{norma.chave}', 'titulo': titulo,
            'sha256': sha, 'markdown_sha256': None, 'markdown_arquivo': None, 'original': f'original.{extensao}',
            'coletado_em': instante.astimezone(timezone.utc).isoformat(),
            'status': 'coletado' if markdown is not None else 'extracao_pendente',
            'visao_fonte': candidato.visao, 'natureza_documental': 'legislacao', 'vigencia': 'nao_verificada',
            'jurisdicao': jurisdicao, 'norma_chave': norma.chave, 'situacao_fonte': candidato.situacao_fonte,
            'fonte': candidato.fonte, 'rodada': rodada, 'tipo': norma.tipo, 'numero': norma.numero,
            'ano': achada[2] if achada else norma.ano}
    documento = None
    if markdown is not None:
        documento = '\n'.join(['---', f'source_url: {candidato.url}', f'sha256: {sha}',
                               f'coletado_em: {meta["coletado_em"]}', 'vigencia: nao_verificada', '---', '',
                               f'# {titulo}', '', f'[Arquivo original]({meta["original"]})', '',
                               '> Coletado para pesquisa. A data de coleta não comprova vigência; a situação '
                               'declarada pela fonte consta em metadados.json.', '', markdown, '']).encode('utf-8')
        meta['markdown_arquivo'] = 'documento.md'
        meta['markdown_sha256'] = hashlib.sha256(documento).hexdigest()
    pasta.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.coleta-', dir=pasta))
    try:
        (staging / meta['original']).write_bytes(raw)
        if documento is not None:
            (staging / 'documento.md').write_bytes(documento)
        (staging / 'metadados.json').write_bytes(json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
        try:
            staging.rename(alvo)
        except OSError:  # coleta concorrente da mesma versao
            if not alvo.exists():
                raise
            _confere_existente(alvo, raw)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return alvo
