from pathlib import Path

import httpx
import pytest

from backend.crawler.fontes_normas import (
    FONTES_FEDERAIS, USER_AGENT, Bloqueada, Camara, Http, Indisponivel, Lexml, Planalto, decodificar,
)
from backend.crawler.normas_id import NormaId

FIX = Path(__file__).parent / 'fixtures' / 'normas'


def fx(nome: str) -> bytes:
    return (FIX / nome).read_bytes()


class Relogio:
    def __init__(self):
        self.t = 1000.0
        self.pausas: list[float] = []

    def agora(self):
        return self.t

    def dormir(self, s):
        self.pausas.append(s)
        self.t += s


def montar(rotas: dict, atraso=0.0, atrasos=None):
    """rotas: url -> (status, corpo, content-type). Ausente = 404. Devolve (Http, lista de URLs pedidas, relogio)."""
    pedidos: list[str] = []
    rel = Relogio()

    def handler(req: httpx.Request) -> httpx.Response:
        pedidos.append(str(req.url))
        assert 'python-requests' not in req.headers['user-agent'].lower() and '@' not in req.headers['user-agent']
        st, corpo, ct = rotas.get(str(req.url), (404, b'', 'text/html'))
        return httpx.Response(st, content=corpo, headers={'content-type': ct})

    http = Http(httpx.Client(transport=httpx.MockTransport(handler)), atraso=atraso, atrasos=atrasos,
                relogio=rel.agora, dormir=rel.dormir)
    return http, pedidos, rel


LEI = NormaId('lei', 10833, 2003, 'federal')
DEC = NormaId('decreto', 70235, 1972, 'federal')
PL = 'https://www.planalto.gov.br/ccivil_03/'


def test_user_agent_generico():
    assert 'python-requests' not in USER_AGENT.lower() and '@' not in USER_AGENT


def test_decodificar_cp1252_sem_charset_e_utf8():
    assert decodificar('Contribuição'.encode('cp1252'), None) == 'Contribuição'
    assert decodificar('Contribuição'.encode('utf-8'), None) == 'Contribuição'
    assert decodificar('Contribuição'.encode('cp1252'), 'iso-8859-1') == 'Contribuição'
    assert decodificar('Contribuição'.encode('utf-8'), 'utf-8') == 'Contribuição'


def test_planalto_windows_1252_preserva_acentos():
    raw = fx('planalto_lei_10833_compilado.raw')
    http, _, _ = montar({PL + 'leis/2003/l10.833.htm': (200, raw, 'text/html')})
    # fixture e cp1252 puro: utf-8 estrito falha
    with pytest.raises(UnicodeDecodeError):
        raw.decode('utf-8')
    from backend.crawler.fontes_normas import texto
    resp = http.get(PL + 'leis/2003/l10.833.htm')
    t = texto(resp)
    assert 'Contribuição' in t and '�' not in t and 'Ã§' not in t
    c = Planalto().localizar(LEI, http)
    assert [x.url for x in c] == [PL + 'leis/2003/l10.833.htm'] and c[0].visao == 'unica'
    assert c[0].situacao_fonte is None


def test_planalto_decreto_so_como_cons_percorre_candidatos():
    http, pedidos, _ = montar({PL + 'decreto/d70235cons.htm': (200, fx('planalto_decreto_70235.raw'), 'text/html')})
    c = Planalto().localizar(DEC, http)
    assert [(x.url, x.visao) for x in c] == [(PL + 'decreto/d70235cons.htm', 'compilada')]
    assert PL + 'decreto/antigos/d70235.htm' in pedidos and PL + 'decreto/d70235.htm' in pedidos


@pytest.mark.parametrize('norma,esperado', [
    (NormaId('lei', 4320, 1964, 'federal'), 'leis/l4320.htm'),
    (NormaId('lei', 10637, 2002, 'federal'), 'leis/2002/l10637.htm'),
    (NormaId('lei', 10865, 2004, 'federal'), '_ato2004-2006/2004/lei/l10.865.htm'),
    (NormaId('lei', 14592, 2023, 'federal'), '_ato2023-2026/2023/lei/l14592.htm'),
    (NormaId('lc', 123, 2006, 'federal'), 'leis/lcp/lcp123.htm'),
    (NormaId('decreto', 3000, 1999, 'federal'), 'decreto/d3000.htm'),
    (NormaId('decreto', 4544, 2002, 'federal'), 'decreto/2002/d4544.htm'),
    (NormaId('decreto', 9580, 2018, 'federal'), '_ato2015-2018/2018/decreto/d9580.htm'),
    (NormaId('dl', 406, 1968, 'federal'), 'decreto-lei/del0406.htm'),
    (NormaId('mp', 1185, 2023, 'federal'), '_ato2023-2026/2023/mpv/mpv1185.htm'),
])
def test_planalto_regras_de_url(norma, esperado):
    assert esperado in Planalto.caminhos(norma)


def test_planalto_sem_ano_ou_mp_antiga_nao_deriva_url():
    assert Planalto.caminhos(NormaId('lei', 10833, None, 'federal')) == []
    assert Planalto.caminhos(NormaId('mp', 2158, 2001, 'federal')) == []


def test_aceita_so_federal_e_tipos_cobertos():
    assert not Planalto().aceita(NormaId('portaria', 1, 2020, 'federal', 'rfb'))
    assert not Planalto().aceita(NormaId('lei', 1, 2020, 'df'))
    assert Planalto().aceita(LEI) and Lexml().aceita(LEI) and Camara().aceita(LEI)
    assert not Lexml().aceita(NormaId('dl', 406, 1968, 'federal'))


def test_nao_encontrado_retorna_lista_vazia():
    rotas = {
        'https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2003;99999': (200, fx('lexml_naoencontrado.raw'), 'text/html'),
    }
    http, _, _ = montar(rotas)
    n = NormaId('lei', 99999, 2003, 'federal')
    assert Planalto().localizar(n, http) == []  # tudo 404
    assert Lexml().localizar(n, http) == []  # 200 soft 404


def test_camara_busca_vazia_200():
    busca = ('https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal'
             '&geral=lei+99999')
    http, _, _ = montar({busca: (200, fx('camara_busca_naoencontrado.raw'), 'text/html; charset=utf-8')})
    assert Camara().localizar(NormaId('lei', 99999, 2003, 'federal'), http) == []


def test_fonte_localiza_compilada_e_original():
    busca = ('https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal'
             '&geral=lei+10833')
    norma = ('https://www2.camara.leg.br/legin/fed/lei/2003/'
             'lei-10833-29-dezembro-2003-497045-norma-pl.html')
    http, pedidos, _ = montar({
        busca: (200, fx('camara_busca_lei10833.raw'), 'text/html; charset=utf-8'),
        norma: (200, fx('camara_lei_10833.raw'), 'text/html; charset=utf-8'),
    })
    c = Camara().localizar(LEI, http)
    base = 'https://www2.camara.leg.br/legin/fed/lei/2003/lei-10833-29-dezembro-2003-497045-'
    assert {(x.visao, x.url) for x in c} == {
        ('compilada', base + 'normaatualizada-pl.html'),
        ('original', base + 'publicacaooriginal-1-pl.html'),
    }
    assert all(x.fonte == 'camara' and x.situacao_fonte == 'Não consta revogação expressa' for x in c)
    # decretos 5062/7455/10833 da busca por texto foram descartados por tipo/numero/ano
    assert not any('decreto' in p for p in pedidos if 'legin' in p)


def test_camara_decreto_confere_numero_e_ano():
    busca = ('https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal'
             '&geral=decreto+70235')
    norma = ('https://www2.camara.leg.br/legin/fed/decret/1970-1979/'
             'decreto-70235-6-marco-1972-418562-norma-pe.html')
    http, _, _ = montar({
        busca: (200, fx('camara_busca_decreto70235.raw'), 'text/html; charset=utf-8'),
        norma: (200, fx('camara_decreto_70235.raw'), 'text/html; charset=utf-8'),
    })
    assert len(Camara().localizar(DEC, http)) >= 1
    # ano errado: nada
    http2, _, _ = montar({busca: (200, fx('camara_busca_decreto70235.raw'), 'text/html; charset=utf-8')})
    assert Camara().localizar(NormaId('decreto', 70235, 1999, 'federal'), http2) == []


def test_lexml_traz_links_da_camara_https():
    url = 'https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2003;10833'
    http, _, _ = montar({url: (200, fx('lexml_urn_lei10833.raw'), 'text/html; charset=utf-8')})
    c = Lexml().localizar(LEI, http)
    assert {x.visao for x in c} == {'original', 'compilada'}
    assert all(x.url.startswith('https://www2.camara.leg.br/legin/fed/lei/2003/') for x in c)
    assert all(x.fonte == 'lexml' and x.situacao_fonte is None for x in c)


def test_federais_ordem():
    assert [f.nome for f in FONTES_FEDERAIS] == ['planalto', 'lexml', 'camara']


ROBOTS_LEX = 'User-agent: *\nDisallow: /busca/\nAllow: /urn\n'


def test_robots_proibido_levanta_bloqueada_sem_baixar():
    http, pedidos, _ = montar({'https://www.lexml.gov.br/robots.txt': (200, ROBOTS_LEX.encode(), 'text/plain')})
    with pytest.raises(Bloqueada):
        http.get('https://www.lexml.gov.br/busca/?q=x')
    assert [p for p in pedidos if '/busca/' in p] == []
    assert http.get('https://www.lexml.gov.br/urn/x').status_code == 404  # permitido
    assert pedidos.count('https://www.lexml.gov.br/robots.txt') == 1  # cache por host


def test_robots_html_ou_404_nao_bloqueia():
    spa = (b'<!doctype html><html><body>app</body></html>')
    http, _, _ = montar({'https://normas.receita.fazenda.gov.br/robots.txt': (200, spa, 'text/html')})
    assert http.get('https://normas.receita.fazenda.gov.br/x').status_code == 404


def test_403_levanta_bloqueada():
    http, _, _ = montar({PL + 'leis/l1.htm': (403, b'no', 'text/html')})
    with pytest.raises(Bloqueada):
        http.get(PL + 'leis/l1.htm')


def test_429_recua_e_depois_bloqueia():
    n = {'c': 0}
    rel = Relogio()
    def h(req):
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        n['c'] += 1
        return httpx.Response(429 if n['c'] < 2 else 200, content=b'ok')
    http = Http(httpx.Client(transport=httpx.MockTransport(h)), atraso=1, relogio=rel.agora, dormir=rel.dormir)
    assert http.get('https://x.test/a').status_code == 200 and 60.0 in rel.pausas
    http2 = Http(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404 if r.url.path == '/robots.txt' else 429))),
                 atraso=1, relogio=rel.agora, dormir=rel.dormir)
    with pytest.raises(Bloqueada):
        http2.get('https://x.test/a')


def test_limite_por_host():
    http, _, rel = montar({}, atraso=1.0, atrasos={'www.camara.leg.br': 6.0})
    http.get('https://a.test/1')  # robots.txt + pedido: o segundo espera 1 s
    assert rel.pausas == [1.0]
    rel.pausas.clear()
    http.get('https://a.test/2')
    assert rel.pausas == [1.0]
    rel.pausas.clear()
    http.get('https://www2.camara.leg.br/x')  # outro host: robots sem espera; www2 e www dividem relogio
    http.get('https://www.camara.leg.br/y')
    assert rel.pausas == [6.0, 6.0, 6.0]  # www2 e www dividem o mesmo relogio de host


def _http_fn(h, atraso=0.0):
    rel = Relogio()
    return Http(httpx.Client(transport=httpx.MockTransport(h)), atraso=atraso, relogio=rel.agora, dormir=rel.dormir), rel


def test_5xx_tenta_de_novo_e_depois_indisponivel():
    n = {'c': 0}
    def h(req):
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        n['c'] += 1
        return httpx.Response(503)
    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get('https://x.test/a')
    assert n['c'] == 2
    # uma falha e sucesso na segunda: ok
    k = {'c': 0}
    def h2(req):
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        k['c'] += 1
        return httpx.Response(500 if k['c'] == 1 else 200, content=b'ok')
    http2, _ = _http_fn(h2)
    assert http2.get('https://x.test/a').status_code == 200


def test_erro_de_rede_e_timeout_viram_indisponivel():
    def h(req):
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        raise httpx.ConnectTimeout('lento')
    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get('https://x.test/a')


def test_localizar_propaga_indisponivel_e_nunca_devolve_vazio():
    h = lambda req: httpx.Response(404 if req.url.path == '/robots.txt' else 502)
    http, _ = _http_fn(h)
    for f in (Planalto(), Lexml(), Camara()):
        with pytest.raises(Indisponivel):
            f.localizar(LEI, http)


def test_camara_busca_com_status_inesperado_e_indisponivel():
    busca = ('https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal&geral=lei+10833')
    http, _, _ = montar({busca: (404, b'x', 'text/html')})
    with pytest.raises(Indisponivel):
        Camara().localizar(LEI, http)


def test_lexml_status_inesperado_e_indisponivel():
    http, _, _ = montar({'https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2003;10833': (500, b'', 'text/html')})
    with pytest.raises(Indisponivel):
        Lexml().localizar(LEI, http)


def test_robots_5xx_nega_e_nao_guarda_cache():
    n = {'robots': 0, 'x': 0}
    def h(req):
        if req.url.path == '/robots.txt':
            n['robots'] += 1
            return httpx.Response(500 if n['robots'] <= 2 else 404)
        n['x'] += 1
        return httpx.Response(200, content=b'ok')
    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get('https://x.test/a')
    assert n['x'] == 0  # negado sem baixar
    assert http.get('https://x.test/a').status_code == 200  # nao ficou em cache
    assert n['robots'] == 3


def test_robots_401_403_bloqueia_e_guarda_sem_nova_requisicao():
    n = {'robots': 0, 'x': 0}
    def h(req):
        if req.url.path == '/robots.txt':
            n['robots'] += 1
            return httpx.Response(403)
        n['x'] += 1
        return httpx.Response(200)
    http, _ = _http_fn(h)
    for _ in range(3):
        with pytest.raises(Bloqueada):
            http.get('https://x.test/a')
    assert n == {'robots': 1, 'x': 0}


def test_robots_404_libera():
    http, pedidos, _ = montar({PL + 'leis/l1.htm': (200, b'ok', 'text/html')})
    assert http.get(PL + 'leis/l1.htm').status_code == 200


def test_redirect_manual_segue_ate_5_saltos_com_atraso_e_robots_a_cada_um():
    rel = Relogio()
    visto = []
    def h(req):
        visto.append(req.url.path)
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        n = int(req.url.path[1:])
        return httpx.Response(301, headers={'location': f'/{n + 1}'}) if n < 3 else httpx.Response(200, content=b'fim')
    http = Http(httpx.Client(transport=httpx.MockTransport(h)), atraso=2.0, relogio=rel.agora, dormir=rel.dormir)
    assert http.get('https://x.test/1').content == b'fim'
    assert visto == ['/robots.txt', '/1', '/2', '/3']
    assert rel.pausas == [2.0, 2.0, 2.0]  # atraso em cada salto (robots foi o primeiro pedido)


def test_redirect_para_caminho_proibido_levanta_bloqueada_sem_requisicao():
    visto = []
    def h(req):
        visto.append(req.url.path)
        if req.url.path == '/robots.txt':
            return httpx.Response(200, content=b'User-agent: *\nDisallow: /privado/\n')
        return httpx.Response(302, headers={'location': '/privado/x'})
    http, _ = _http_fn(h)
    with pytest.raises(Bloqueada):
        http.get('https://x.test/a')
    assert '/privado/x' not in visto


def test_redirect_para_outro_host_respeita_robots_do_destino():
    visto = []
    def h(req):
        visto.append(str(req.url))
        if req.url.path == '/robots.txt' and req.url.host == 'b.test':
            return httpx.Response(200, content=b'User-agent: *\nDisallow: /\n')
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        return httpx.Response(301, headers={'location': 'https://b.test/z'})
    http, _ = _http_fn(h)
    with pytest.raises(Bloqueada):
        http.get('https://a.test/a')
    assert 'https://b.test/z' not in visto


def test_redirect_excesso_de_saltos_e_indisponivel():
    h = lambda req: httpx.Response(404) if req.url.path == '/robots.txt' else httpx.Response(301, headers={'location': '/loop'})
    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get('https://x.test/loop')


def test_429_honra_retry_after_com_teto_300():
    def mk(valor):
        n = {'c': 0}
        def h(req):
            if req.url.path == '/robots.txt':
                return httpx.Response(404)
            n['c'] += 1
            return httpx.Response(429, headers={'retry-after': valor}) if n['c'] == 1 else httpx.Response(200)
        return h
    http, rel = _http_fn(mk('7'))
    assert http.get('https://x.test/a').status_code == 200 and 7.0 in rel.pausas and 60.0 not in rel.pausas
    http, rel = _http_fn(mk('9999'))
    http.get('https://x.test/a')
    assert 300.0 in rel.pausas
    http, rel = _http_fn(mk('Wed, 21 Oct 2026 07:28:00 GMT'))  # data HTTP: usa o recuo padrao
    http.get('https://x.test/a')
    assert 60.0 in rel.pausas
