"""Localizacao de normas federais: cliente HTTP educado e estrategias por fonte (sem rede nos testes)."""
import re
import time
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from backend.crawler.normas_id import NormaId

USER_AGENT = 'Mozilla/5.0 (compatible; acervo-pesquisa-bot/0.1)'
_ROBOTS_AGENTE = 'acervo-pesquisa-bot'
# docs/fontes-normas.md, "Atrasos e limites por host"; www2.camara conta como www.camara
ATRASOS = {
    'www.planalto.gov.br': 1.5, 'www.camara.leg.br': 6.0, 'www.lexml.gov.br': 5.0,
    'normas.receita.fazenda.gov.br': 1.5, 'normasinternet2.receita.fazenda.gov.br': 1.5,
    'www.sinj.df.gov.br': 2.0, 'www.confaz.fazenda.gov.br': 2.0,
}
_RECUO_429 = 60.0
_RETRY_AFTER_MAX = 300.0
_MAX_SALTOS = 5


class Bloqueada(Exception):
    """Fonte proibiu (robots.txt) ou recusou (401/403/429 persistente). Nao contornar."""


class Indisponivel(Exception):
    """5xx, falha de rede ou timeout apos uma nova tentativa. Nunca significa 'norma ausente'."""


def decodificar(raw: bytes, charset_declarado: str | None) -> str:
    """Charset declarado vence; sem declaracao tenta UTF-8 e cai para cp1252 (Planalto)."""
    cs = (charset_declarado or '').lower().replace('_', '-')
    if cs in ('iso-8859-1', 'latin-1', 'latin1', 'windows-1252'):
        cs = 'cp1252'  # como os navegadores: iso-8859-1 declarado e cp1252 de fato
    if cs:
        try:
            return raw.decode(cs, errors='replace')
        except LookupError:
            pass
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace')


def texto(resp: httpx.Response) -> str:
    return decodificar(resp.content, resp.charset_encoding)


def _chave_host(host: str) -> str:
    return 'www.camara.leg.br' if host == 'www2.camara.leg.br' else host


class Http:
    """GET com atraso por host, robots.txt em cache por host, redirecionamento manual e erros tipados."""

    def __init__(self, client: httpx.Client, atraso: float = 2.0, atrasos: dict[str, float] | None = None,
                 relogio: Callable[[], float] = time.monotonic, dormir: Callable[[float], None] = time.sleep):
        self.client, self.atraso, self.relogio, self.dormir = client, atraso, relogio, dormir
        self.atrasos = {**ATRASOS, **(atrasos or {})}
        self._ultimo: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | Bloqueada] = {}

    def _pedir(self, url: str) -> httpx.Response:
        """Um salto, sem seguir redirecionamento. 429: recua e tenta de novo; 5xx/rede: tenta de novo."""
        host = _chave_host(urlsplit(url).netloc)
        for tentativa in (1, 2):
            espera = self._ultimo.get(host, -1e9) + self.atrasos.get(host, self.atraso) - self.relogio()
            if espera > 0:
                self.dormir(espera)
            try:
                resp = self.client.get(url, headers={'User-Agent': USER_AGENT}, follow_redirects=False)
            except httpx.TransportError as e:  # inclui timeouts
                self._ultimo[host] = self.relogio()
                if tentativa == 2:
                    raise Indisponivel(f'{type(e).__name__} em {url}') from e
                continue
            self._ultimo[host] = self.relogio()
            if resp.status_code == 429 and tentativa == 1:
                self.atrasos[host] = 2 * self.atrasos.get(host, self.atraso)
                self.dormir(_espera_429(resp))
                continue
            if resp.status_code in (401, 403, 429):
                raise Bloqueada(f'{resp.status_code} em {url}')
            if resp.status_code >= 500:
                if tentativa == 2:
                    raise Indisponivel(f'{resp.status_code} em {url}')
                continue
            return resp
        raise AssertionError('inalcancavel')

    def _seguir(self, url: str, checar_robots: bool) -> httpx.Response:
        for _ in range(_MAX_SALTOS + 1):
            if checar_robots and not self._permitido(url):
                raise Bloqueada(f'robots.txt proibe {url}')
            resp = self._pedir(url)
            loc = resp.headers.get('location')
            if resp.status_code in (301, 302, 303, 307, 308) and loc:
                url = urljoin(url, loc)  # proximo salto repete robots e atraso do host de destino
                continue
            return resp
        raise Indisponivel(f'mais de {_MAX_SALTOS} redirecionamentos')

    def _permitido(self, url: str) -> bool:
        p = urlsplit(url)
        base = f'{p.scheme}://{p.netloc}'
        if base not in self._robots:
            try:
                resp = self._seguir(base + '/robots.txt', checar_robots=False)
            except Bloqueada as e:  # 401/403: guardado, sem nova requisicao
                self._robots[base] = e
                raise
            # Indisponivel (5xx/rede) propaga sem cache: nega agora, tenta de novo depois
            rp = RobotFileParser()
            # 404/outros 4xx ou SPA devolvendo HTML: sem politica publicada, sem regras
            rp.parse(texto(resp).splitlines() if resp.status_code == 200 else [])
            self._robots[base] = rp
        rp = self._robots[base]
        if isinstance(rp, Bloqueada):
            raise rp
        # ponytail: robotparser da stdlib nao entende curingas (/*.pdf); nunca baixamos PDF
        return rp.can_fetch(_ROBOTS_AGENTE, url)

    def get(self, url: str) -> httpx.Response:
        return self._seguir(url, checar_robots=True)


def _espera_429(resp: httpx.Response) -> float:
    try:
        return min(max(float(resp.headers['retry-after']), 0.0), _RETRY_AFTER_MAX)
    except (KeyError, ValueError):  # ausente ou data HTTP
        return _RECUO_429


def exigir(resp: httpx.Response, *aceitos: int) -> httpx.Response:
    """Status fora dos documentados nao prova ausencia: Indisponivel."""
    if resp.status_code not in aceitos:
        raise Indisponivel(f'status {resp.status_code} em {resp.url}')
    return resp


@dataclass(frozen=True)
class Candidato:
    url: str
    fonte: str
    visao: str  # compilada | original | unica
    situacao_fonte: str | None = None  # so quando a fonte informa expressamente


class Fonte(Protocol):
    nome: str

    def aceita(self, norma: NormaId) -> bool: ...

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]: ...


_CICLOS = [(2004, '2004-2006'), (2007, '2007-2010'), (2011, '2011-2014'),
           (2015, '2015-2018'), (2019, '2019-2022'), (2023, '2023-2026')]


def _ciclo(ano: int) -> str | None:
    c = None
    for ini, nome in _CICLOS:
        if ano >= ini:
            c = nome
    return c


def _milhar(n: int) -> str:
    return f'{n:,}'.replace(',', '.')


class Planalto:
    nome = 'planalto'
    _BASE = 'https://www.planalto.gov.br/ccivil_03/'
    _TIPOS = {'lei', 'lc', 'decreto', 'dl', 'mp'}

    def aceita(self, norma: NormaId) -> bool:
        return norma.jurisdicao == 'federal' and norma.tipo in self._TIPOS

    @staticmethod
    def caminhos(norma: NormaId) -> list[str]:
        """Candidatos em ordem (era, compilado, cons, ponto de milhar). Sem ano nao ha como derivar."""
        n, a, t = norma.numero, norma.ano, norma.tipo
        if a is None:
            return []
        if t == 'lc':
            return [f'leis/lcp/lcp{n}.htm', f'leis/lcp/lcp{n}compilado.htm']
        if t == 'dl':
            return list(dict.fromkeys([f'decreto-lei/del{n:04d}.htm', f'decreto-lei/del{n:04d}compilado.htm',
                                       f'decreto-lei/del{n}compilado.htm']))
        if t == 'mp':  # antes de 2004 a URL depende da reedicao, que a citacao nao traz
            c = _ciclo(a)
            return [f'_ato{c}/{a}/mpv/mpv{n}.htm'] if c else []
        ns = [str(n)] + ([_milhar(n)] if n >= 1000 else [])
        if t == 'lei':
            if a <= 2000:
                pastas = ['leis/']
            elif a <= 2003:
                pastas = [f'leis/{a}/']
            else:
                pastas = [f'_ato{_ciclo(a)}/{a}/lei/']
            letra = 'l'
        else:  # decreto
            if a <= 1994:
                pastas = ['decreto/antigos/', 'decreto/']
            elif a <= 2001:
                pastas = ['decreto/']
            elif a <= 2003:
                pastas = [f'decreto/{a}/']
            else:
                pastas = [f'_ato{_ciclo(a)}/{a}/decreto/']
            letra = 'd'
        out = [f'{p}{letra}{x}.htm' for p in pastas for x in ns]
        out += [f'{p}{letra}{n}{suf}.htm' for p in pastas for suf in ('compilado', 'compilada', 'cons')]
        return out

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]:
        for c in self.caminhos(norma):
            url = self._BASE + c
            if exigir(http.get(url), 200, 404).status_code == 200:
                visao = 'compilada' if re.search(r'(compilad[oa]|cons)\.htm$', c) else 'unica'
                return [Candidato(url, self.nome, visao)]
        return []


class Lexml:
    """Ficha da URN: nao serve texto, so a ponte para os links da Camara (id opaco)."""
    nome = 'lexml'
    _TIPO = {'lei': 'lei', 'lc': 'lei.complementar', 'decreto': 'decreto', 'mp': 'medida.provisoria'}

    def aceita(self, norma: NormaId) -> bool:
        return norma.jurisdicao == 'federal' and norma.tipo in self._TIPO and norma.ano is not None

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]:
        urn = f'urn:lex:br:federal:{self._TIPO[norma.tipo]}:{norma.ano};{norma.numero}'
        resp = exigir(http.get('https://www.lexml.gov.br/urn/' + quote(urn, safe=':;.')), 200)
        html = texto(resp)
        if 'Nome Uniforme' not in html:  # 200 de ~1 KB e soft 404
            return []
        links = re.findall(r'href="(https?://www2\.camara\.gov\.br/legin/fed/[^"]+\.html)"', html)
        saida = []
        for link in dict.fromkeys(links):
            link = link.replace('http://www2.camara.gov.br', 'https://www2.camara.leg.br')
            if '-publicacaooriginal-' in link:
                saida.append(Candidato(link, self.nome, 'original'))
            elif '-norma-' in link:  # a pagina de dados lista o texto atualizado com o mesmo radical
                saida.append(Candidato(re.sub(r'-norma-(p[le])\.html$', r'-normaatualizada-\1.html', link),
                                       self.nome, 'compilada'))
        return saida


class Camara:
    nome = 'camara'
    _PASTA = {'lei': 'lei', 'lc': 'leicom', 'dl': 'declei', 'decreto': 'decret', 'mp': 'medpro'}
    _BUSCA = {'lei': 'lei', 'lc': 'lei complementar', 'dl': 'decreto-lei', 'decreto': 'decreto',
              'mp': 'medida provisória'}
    _ARQ = re.compile(r'-(\d+)-\d{1,2}-[a-zç]+-(\d{4})-\d+-norma-p[le]\.html$')

    def aceita(self, norma: NormaId) -> bool:
        return norma.jurisdicao == 'federal' and norma.tipo in self._PASTA

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]:
        q = urlencode({'abrangencia': 'Legislação Federal', 'geral': f'{self._BUSCA[norma.tipo]} {norma.numero}'})
        html = texto(exigir(http.get('https://www.camara.leg.br/legislacao/busca?' + q), 200))
        pasta = f'/legin/fed/{self._PASTA[norma.tipo]}/'
        achadas = []
        paginas = re.findall(r'href="(https://www2\.camara\.leg\.br/legin/fed/[^"]+-norma-p[le]\.html)"', html)
        for u in dict.fromkeys(paginas):
            m = self._ARQ.search(u)  # a busca e por texto: conferir tipo (pasta), numero e ano
            if pasta in u and m and int(m[1]) == norma.numero and (norma.ano is None or int(m[2]) == norma.ano):
                achadas.append(u)
        saida = []
        for u in achadas:
            resp = exigir(http.get(u), 200, 404)
            if resp.status_code == 404:
                continue
            pag = texto(resp)
            sit = re.search(r'Situa\S*\s*:\s*</strong></span>\s*<span>([^<]+)</span>', pag)
            sit = sit[1].strip() if sit else None
            rels = re.findall(r'href="([^"]*-(?:normaatualizada|publicacaooriginal-\d+)-p[le]\.html)"', pag)
            for rel in dict.fromkeys(rels):
                visao = 'compilada' if '-normaatualizada-' in rel else 'original'
                saida.append(Candidato(urljoin(u, rel), self.nome, visao, sit))
        return saida


FONTES_FEDERAIS: list[Fonte] = [Planalto(), Lexml(), Camara()]
