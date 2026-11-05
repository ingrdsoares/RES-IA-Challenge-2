"""Identidade de norma: (jurisdicao, tipo, orgao, numero, ano) a partir de um titulo."""
import re
import unicodedata
from dataclasses import dataclass

_TIPOS = [
    ('lc', r'lei\s+complementar|lcp?'),
    ('dl', r'decreto[\s-]+lei|dl'),
    ('ec', r'emenda\s+constitucional|ec'),
    ('mp', r'medida\s+provisoria|mpv?'),
    ('lei', r'lei(?:\s+ordinaria)?'),
    ('decreto', r'decreto'),
    ('in', r'instrucao\s+normativa|in'),
    ('portaria', r'portaria|port\.?'),
    ('ade', r'ato\s+declaratorio\s+executivo|ade'),
    ('resol_cgsn', r'resolucao(?:\s+cgsn)?|resol\.?(?:\s+cgsn)?'),
    ('convenio_icms', r'convenio\s+icms'),
    ('ajuste_sinief', r'ajuste\s+sinief'),
]
_ORG = r'(?:rfb|srf|pgfn|sefaz|cosit|coana)'
_RX = re.compile(
    r'\b(?:' + '|'.join(f'(?P<{k}>{p})' for k, p in _TIPOS) + r')'
    r'(?:\s+(?P<jur>df|distrital|federal|gdf))?'
    rf'(?:\s+conjunta)?(?:\s+(?P<orgao>{_ORG}(?:/{_ORG})*))?'
    r'\s*(?P<marc>n[o°º.]*)?\s*(?P<num>\d{1,3}(?:\.\d{3})+|\d{1,6})'
    r'(?:\s*/\s*(?P<a1>\d{4}|\d{2})\b|,?\s+de\s+(?:\d{1,2}[o°º]?\s+de\s+[a-z]+\s+de\s+)?(?P<a2>\d{4})\b)?'
)
_CONFAZ = {'convenio_icms', 'ajuste_sinief'}


@dataclass(frozen=True)
class NormaId:
    tipo: str
    numero: int
    ano: int | None
    jurisdicao: str
    orgao: str | None = None

    @property
    def chave(self) -> str:
        return f"{self.jurisdicao}:{self.tipo}:{self.orgao or '-'}:{self.numero}:{self.ano or '?'}"


def _sem_acento(t: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', t).lower() if not unicodedata.combining(c))


def norma_do_match(m: re.Match, jurisdicao: str) -> NormaId:
    """Monta NormaId a partir de um match de _RX (jurisdicao ja decidida pelo chamador)."""
    tipo = next(k for k, _ in _TIPOS if m.group(k))
    a = m.group('a1') or m.group('a2')
    ano = int(a) if a else None
    if ano is not None and ano < 100:
        ano += 2000 if ano < 40 else 1900
    if tipo in _CONFAZ:
        jurisdicao = 'confaz'
    return NormaId(tipo, int(m.group('num').replace('.', '')), ano, jurisdicao, m.group('orgao'))


def identidade_titulo(titulo: str, jurisdicao: str = 'indefinida') -> NormaId | None:
    t = _sem_acento(titulo)
    m = _RX.match(t.strip())
    if not m:
        return None
    if re.search(r'\bdf\b|\bgdf\b|distrit', t):
        jurisdicao = 'df'
    return norma_do_match(m, jurisdicao)
