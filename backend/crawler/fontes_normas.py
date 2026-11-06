"""Localizacao de normas federais: cliente HTTP educado e estrategias por fonte (sem rede nos testes)."""
import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from backend.crawler.consultas_rfb import search_payload
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
        self._travas: dict[str, threading.Lock] = {}
        self._travas_mestre = threading.Lock()

    def _trava(self, chave: str) -> threading.Lock:
        with self._travas_mestre:
            return self._travas.setdefault(chave, threading.Lock())

    def _pedir(self, url: str, corpo: dict | None = None) -> httpx.Response:
        """Um salto, sem seguir redirecionamento. 429: recua e tenta de novo; 5xx/rede: tenta de novo."""
        host = _chave_host(urlsplit(url).netloc)
        with self._trava(host):  # atraso por host vale entre threads; hosts diferentes seguem em paralelo
            return self._pedir_travado(url, corpo, host)

    def _pedir_travado(self, url: str, corpo: dict | None, host: str) -> httpx.Response:
        for tentativa in (1, 2):
            espera = self._ultimo.get(host, -1e9) + self.atrasos.get(host, self.atraso) - self.relogio()
            if espera > 0:
                self.dormir(espera)
            try:
                cab = {'User-Agent': USER_AGENT}
                resp = (self.client.get(url, headers=cab, follow_redirects=False) if corpo is None
                        else self.client.post(url, json=corpo, headers=cab, follow_redirects=False))
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

    def _seguir(self, url: str, checar_robots: bool, corpo: dict | None = None) -> httpx.Response:
        for _ in range(_MAX_SALTOS + 1):
            if checar_robots and not self._permitido(url):
                raise Bloqueada(f'robots.txt proibe {url}')
            resp = self._pedir(url, corpo)
            loc = resp.headers.get('location')
            if resp.status_code in (301, 302, 303, 307, 308) and loc:
                url = urljoin(url, loc)  # proximo salto repete robots e atraso do host de destino
                continue
            return resp
        raise Indisponivel(f'mais de {_MAX_SALTOS} redirecionamentos')

    def _permitido(self, url: str) -> bool:
        p = urlsplit(url)
        base = f'{p.scheme}://{p.netloc}'
        with self._trava('robots:' + base):
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

    def post(self, url: str, corpo: dict) -> httpx.Response:
        """POST JSON (so a pesquisa da Receita); mesmas regras de robots, atraso e erros do get."""
        return self._seguir(url, checar_robots=True, corpo=corpo)


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


class Ambigua(Exception):
    """Mais de um ato satisfaz a citacao; nao escolher sozinho. A Task 7 grava situacao 'ambigua' com o motivo."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


class SemTextoAutomatico(Exception):
    """A norma existe (ou nao ha regra de busca), mas nao ha texto que se possa coletar sozinho: a Task 7 grava `manual`."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


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


CONTINUAS = {'lei', 'lc', 'dl', 'decreto'}  # numeracao continua: o numero basta sem o ano


class Planalto:
    nome = 'planalto'
    _BASE = 'https://www.planalto.gov.br/ccivil_03/'
    _TIPOS = {'lei', 'lc', 'decreto', 'dl', 'mp', 'ec', 'constituicao'}

    def aceita(self, norma: NormaId) -> bool:
        return norma.jurisdicao == 'federal' and norma.tipo in self._TIPOS and norma.ano is not None

    @staticmethod
    def caminhos(norma: NormaId) -> list[str]:
        """Candidatos em ordem (era, compilado, cons, ponto de milhar). Sem ano nao ha como derivar."""
        n, a, t = norma.numero, norma.ano, norma.tipo
        if a is None:
            return []
        if t == 'constituicao':
            return ['constituicao/constituicao.htm']
        if t == 'ec':  # emendas anteriores a CF/88 (e a EC 1/1992) nao seguem este padrao verificado
            return [f'constituicao/emendas/emc/emc{n:02d}.htm'] if a >= 1992 else []
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
    _PASTA = {'lei': 'lei', 'lc': 'leicom', 'dl': 'declei', 'decreto': 'decret', 'mp': 'medpro', 'ec': 'emecon',
              'constituicao': 'consti'}
    _BUSCA = {'lei': 'lei', 'lc': 'lei complementar', 'dl': 'decreto-lei', 'decreto': 'decreto',
              'mp': 'medida provisória', 'ec': 'emenda constitucional'}
    _CF = '/legin/fed/consti/1988/constituicao-1988-'
    _PAGINA = re.compile(r'Exibindo resultados de \d+ a (\d+) de (\d+)')
    _ARQ = re.compile(r'-(\d+)-\d{1,2}-[a-zç]+-(\d{4})-\d+-norma-p[le]\.html$')

    def aceita(self, norma: NormaId) -> bool:
        # sem ano so a numeracao continua (docs/fontes-normas.md, "Normas sem ano")
        return (norma.jurisdicao == 'federal' and norma.tipo in self._PASTA
                and (norma.ano is not None or norma.tipo in CONTINUAS))

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]:
        geral = 'constituição federal 1988' if norma.tipo == 'constituicao' else f'{self._BUSCA[norma.tipo]} {norma.numero}'
        q = urlencode({'abrangencia': 'Legislação Federal', 'geral': geral})
        html = texto(exigir(http.get('https://www.camara.leg.br/legislacao/busca?' + q), 200))
        pasta = f'/legin/fed/{self._PASTA[norma.tipo]}/'
        achadas = []
        paginas = re.findall(r'href="(https://www2\.camara\.leg\.br/legin/fed/[^"]+-norma-p[le]\.html)"', html)
        for u in dict.fromkeys(paginas):
            if norma.tipo == 'constituicao':
                if self._CF in u:
                    achadas.append(u)
                continue
            m = self._ARQ.search(u)  # a busca e por texto: conferir tipo (pasta), numero e ano
            if pasta in u and m and int(m[1]) == norma.numero and (norma.ano is None or int(m[2]) == norma.ano):
                achadas.append(u)
        if norma.ano is None:  # so uma norma, e so se a pagina de resultados for a lista inteira
            pag = self._PAGINA.search(html)
            if pag is None:
                raise Ambigua('busca da Camara sem contagem de resultados; unicidade nao verificavel')
            if int(pag[2]) > int(pag[1]):  # nunca nao_encontrada a partir de uma pagina truncada
                raise Ambigua(f'busca da Camara com {pag[2]} resultados e so {pag[1]} na pagina; unicidade nao verificavel')
            if len(achadas) > 1:
                raise Ambigua(f'{len(achadas)} normas da Camara com tipo {norma.tipo} e numero {norma.numero} (ano nao citado)')
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


class Sinj:
    """Datatable JSON do SINJ-DF; so o texto compilado (docs/fontes-normas.md, SINJ-DF)."""
    nome = 'sinj'
    _BUSCA = 'https://www.sinj.df.gov.br/sinj/ashx/Datatable/ResultadoDePesquisaNormaDatatable.ashx?'
    _TEXTO = 'https://www.sinj.df.gov.br/sinj/Norma/'
    _TIPO = {'lei': 'Lei', 'lc': 'Lei Complementar', 'decreto': 'Decreto', 'portaria': 'Portaria',
             'in': 'Instrução Normativa', 'ade': 'Ato Declaratório'}

    def aceita(self, norma: NormaId) -> bool:
        if norma.jurisdicao != 'df':
            return False
        if norma.ano is None:  # sem ano so lei, LC e decreto (numeracao continua; verificado em 2026-11-06)
            return norma.tipo in ('lei', 'lc', 'decreto')
        return norma.tipo in self._TIPO or norma.tipo == 'lodf'

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]:
        lodf = norma.tipo == 'lodf'  # a LODF nao tem numero: busca por numero 0 e ano traz os atos sem numero
        nome = 'Lei Orgânica' if lodf else self._TIPO[norma.tipo]
        completa = lodf or norma.ano is None  # unicidade so se a pagina trouxer todos os registros
        campos = {'tipo_pesquisa': 'norma', 'nm_tipo_norma': nome, 'nr_norma': norma.numero}
        if norma.ano is not None:
            campos['ano_assinatura'] = norma.ano
        q = urlencode({**campos, 'bbusca': 'sinj_norma', 'iDisplayStart': 0,
                       'iDisplayLength': 200 if lodf else 100 if completa else 10, 'sEcho': 1})
        dados = json.loads(exigir(http.get(self._BUSCA + q), 200).content)
        if completa and 'iTotalDisplayRecords' not in dados:  # ausente nao e zero
            raise Indisponivel('resposta do SINJ sem iTotalDisplayRecords')
        if completa and dados['iTotalDisplayRecords'] > len(dados['aaData']):
            raise Ambigua(f"busca do SINJ com {dados['iTotalDisplayRecords']} registros e so {len(dados['aaData'])} "
                          'na pagina: mais resultados que a pagina; unicidade nao verificavel')
        achados = []
        for linha in dados['aaData']:
            r = linha['_source']  # o filtro de tipo da fonte e aproximado: conferir tudo na resposta
            siglas = {o.get('sg_orgao', '').lower() for o in r.get('origens') or []}
            numero_ok = not r['nr_norma'] if lodf else str(r['nr_norma']) == str(norma.numero)
            if (r['nm_tipo_norma'] == nome and numero_ok
                    and (norma.ano is None or str(r.get('dt_assinatura', ''))[-4:] == str(norma.ano))
                    and (not norma.orgao or norma.orgao.lower() in siglas)):
                achados.append(r)
        if len(achados) > 1:
            raise Ambigua(f'{len(achados)} registros do SINJ com tipo {nome}, numero {norma.numero} e ano {norma.ano or "nao citado"}')
        if not achados:
            return []
        if not (achados[0].get('ar_atualizado') or {}).get('filename'):  # a original do SINJ nao e coletada
            raise SemTextoAutomatico(f"registro {achados[0]['ch_norma']} do SINJ sem texto compilado")
        r = achados[0]
        url = f"{self._TEXTO}{r['ch_norma']}/{r['ar_atualizado']['filename']}"
        return [Candidato(url, self.nome, 'compilada', r.get('nm_situacao'))]


class Confaz:
    """Indice anual do CONFAZ: casa o <span> do item e segue o href; nunca monta o nome do arquivo."""
    nome = 'confaz'
    _BASE = 'https://www.confaz.fazenda.gov.br/legislacao/'
    _TIPO = {'convenio_icms': ('convenios', 'CONVÊNIO ICMS'), 'ajuste_sinief': ('ajustes', 'AJUSTE SINIEF')}

    def aceita(self, norma: NormaId) -> bool:
        return norma.jurisdicao == 'confaz' and norma.tipo in self._TIPO and norma.ano is not None

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]:
        pasta, rotulo = self._TIPO[norma.tipo]
        resp = exigir(http.get(f'{self._BASE}{pasta}/{norma.ano}'), 200, 404)
        if resp.status_code == 404:
            return []
        alvo = f'{rotulo} {norma.numero}/{norma.ano % 100:02d}'
        links = []
        for a in BeautifulSoup(texto(resp), 'html.parser').select('li.navTreeItem a[href]'):
            span = a.find('span')
            if span and span.get_text(strip=True) == alvo and not a['href'].endswith('_anterior'):
                links.append(urljoin(str(resp.url), a['href']))
        links = list(dict.fromkeys(links))
        if len(links) > 1:
            raise Ambigua(f'{len(links)} itens do indice do CONFAZ para {alvo}')
        return [Candidato(u, self.nome, 'unica') for u in links]


class Receita:
    """Pesquisa por numero e ano (sem tipo) e filtra a resposta por tipo e orgao (docs/fontes-normas.md, Receita)."""
    nome = 'receita'
    _BUSCA = 'https://normas.receita.fazenda.gov.br/api/indexacao/ato/pesquisar'
    _ATO = 'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/'
    _NOMES = {'portaria': {'Portaria', 'Portaria Normativa', 'Portaria Conjunta'},
              'in': {'Instrução Normativa', 'Instrução Normativa Conjunta'},
              'ade': {'Ato Declaratório Executivo'}, 'resol_cgsn': {'Resolução'}}

    def aceita(self, norma: NormaId) -> bool:
        return norma.jurisdicao == 'federal' and norma.tipo in self._NOMES and norma.ano is not None

    def _atos(self, norma: NormaId, http: Http) -> list[dict]:
        atos, pagina = [], 1
        while True:
            corpo = {**search_payload('', pagina, 100), 'tiposAtosSelecionados': '', 'anoAto': str(norma.ano),
                     'numeroAto': str(norma.numero), 'dataInicio': '', 'dataFim': '', 'orgaosSelecionados': '',
                     'refino': {'tipoAtoFacet': '', 'siglaOrgaoFacet': '', 'anoAtoFacet': '', 'idTipoAtoFacet': ''}}
            dados = json.loads(exigir(http.post(self._BUSCA, corpo), 200).content)
            atos += dados['atos']
            if pagina >= dados['quantidadePaginas']:
                return atos
            pagina += 1

    @staticmethod
    def _situacao(ato: dict) -> str | None:
        declarado = ato.get('textoConsulta') or ato.get('resumoRevogado')
        return declarado or {'1': 'Vigente', '0': 'Não vigente'}.get(str(ato.get('vigente')))

    def localizar(self, norma: NormaId, http: Http) -> list[Candidato]:
        nomes = self._NOMES[norma.tipo]
        orgao = norma.orgao or ('cgsn' if norma.tipo == 'resol_cgsn' else None)
        achados: dict[int, dict] = {}
        for a in self._atos(norma, http):
            siglas = {o['siglaOrgao'].lower() for o in a.get('orgaos') or []}
            if (a['tipoAto']['nomeTipoAto'] in nomes and str(a['numeroAto']) == str(norma.numero)
                    and str(a['anoAto']) == str(norma.ano)
                    and (orgao is None or orgao.lower() in siglas or set(orgao.lower().split('/')) <= siglas)):
                achados.setdefault(a['idAto'], a)
        orgaos = {frozenset(o['siglaOrgao'].lower() for o in a['orgaos']) for a in achados.values()}
        if orgao is None and len(orgaos) > 1:
            raise Ambigua(f'orgao nao informado e {len(achados)} atos de orgaos diferentes com o mesmo numero')
        saida = []  # varios idAto com o mesmo numero e orgao: todos viram candidatos; a identidade no texto decide
        for ato in achados.values():  # a visao multivigente pode dar 406; a original fica como alternativa
            for visao, rotulo in (('multivigente', 'compilada'), ('original', 'original')):
                saida.append(Candidato(f"{self._ATO}{ato['idAto']}/visao/{visao}", self.nome, rotulo,
                                       self._situacao(ato)))
        return saida


FONTES_DF: list[Fonte] = [Sinj()]
FONTES_CONFAZ: list[Fonte] = [Confaz()]
FONTES_RFB: list[Fonte] = [Receita()]
