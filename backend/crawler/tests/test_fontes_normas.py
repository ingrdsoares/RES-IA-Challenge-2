from pathlib import Path

import httpx
import pytest

from backend.crawler.fontes_normas import (
    FONTES_FEDERAIS,
    USER_AGENT,
    Bloqueada,
    Camara,
    Http,
    Indisponivel,
    Lexml,
    Planalto,
    decodificar,
)
from backend.crawler.normas_id import NormaId

FIX = Path(__file__).parent / "fixtures" / "normas"


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


def montar(rotas: dict, atraso=0.0, atrasos=None, corpos=None):
    """rotas: url -> (status, corpo, content-type). Ausente = 404. Devolve (Http, lista de URLs pedidas, relogio)."""
    pedidos: list[str] = []
    rel = Relogio()

    def handler(req: httpx.Request) -> httpx.Response:
        pedidos.append(str(req.url))
        if corpos is not None and req.method == "POST":
            corpos.append(req.content)
        assert (
            "python-requests" not in req.headers["user-agent"].lower()
            and "@" not in req.headers["user-agent"]
        )
        st, corpo, ct = rotas.get(str(req.url), (404, b"", "text/html"))
        return httpx.Response(st, content=corpo, headers={"content-type": ct})

    http = Http(
        httpx.Client(transport=httpx.MockTransport(handler)),
        atraso=atraso,
        atrasos=atrasos,
        relogio=rel.agora,
        dormir=rel.dormir,
    )
    return http, pedidos, rel


LEI = NormaId("lei", 10833, 2003, "federal")
DEC = NormaId("decreto", 70235, 1972, "federal")
PL = "https://www.planalto.gov.br/ccivil_03/"


def test_user_agent_generico():
    assert "python-requests" not in USER_AGENT.lower() and "@" not in USER_AGENT


def test_decodificar_cp1252_sem_charset_e_utf8():
    assert decodificar("Contribuição".encode("cp1252"), None) == "Contribuição"
    assert decodificar("Contribuição".encode("utf-8"), None) == "Contribuição"
    assert decodificar("Contribuição".encode("cp1252"), "iso-8859-1") == "Contribuição"
    assert decodificar("Contribuição".encode("utf-8"), "utf-8") == "Contribuição"


def test_planalto_windows_1252_preserva_acentos():
    raw = fx("planalto_lei_10833_compilado.raw")
    http, _, _ = montar({PL + "leis/2003/l10.833.htm": (200, raw, "text/html")})
    # fixture e cp1252 puro: utf-8 estrito falha
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
    from backend.crawler.fontes_normas import texto

    resp = http.get(PL + "leis/2003/l10.833.htm")
    t = texto(resp)
    assert "Contribuição" in t and "�" not in t and "Ã§" not in t
    c = Planalto().localizar(LEI, http)
    assert [x.url for x in c] == [PL + "leis/2003/l10.833.htm"] and c[0].visao == "unica"
    assert c[0].situacao_fonte is None


def test_planalto_decreto_so_como_cons_percorre_candidatos():
    http, pedidos, _ = montar(
        {PL + "decreto/d70235cons.htm": (200, fx("planalto_decreto_70235.raw"), "text/html")}
    )
    c = Planalto().localizar(DEC, http)
    assert [(x.url, x.visao) for x in c] == [(PL + "decreto/d70235cons.htm", "compilada")]
    assert PL + "decreto/antigos/d70235.htm" in pedidos and PL + "decreto/d70235.htm" in pedidos


@pytest.mark.parametrize(
    "norma,esperado",
    [
        (NormaId("lei", 4320, 1964, "federal"), "leis/l4320.htm"),
        (NormaId("lei", 10637, 2002, "federal"), "leis/2002/l10637.htm"),
        (NormaId("lei", 10865, 2004, "federal"), "_ato2004-2006/2004/lei/l10.865.htm"),
        (NormaId("lei", 14592, 2023, "federal"), "_ato2023-2026/2023/lei/l14592.htm"),
        (NormaId("lc", 123, 2006, "federal"), "leis/lcp/lcp123.htm"),
        (NormaId("decreto", 3000, 1999, "federal"), "decreto/d3000.htm"),
        (NormaId("decreto", 4544, 2002, "federal"), "decreto/2002/d4544.htm"),
        (NormaId("decreto", 9580, 2018, "federal"), "_ato2015-2018/2018/decreto/d9580.htm"),
        (NormaId("dl", 406, 1968, "federal"), "decreto-lei/del0406.htm"),
        (NormaId("mp", 1185, 2023, "federal"), "_ato2023-2026/2023/mpv/mpv1185.htm"),
    ],
)
def test_planalto_regras_de_url(norma, esperado):
    assert esperado in Planalto.caminhos(norma)


def test_planalto_sem_ano_ou_mp_antiga_nao_deriva_url():
    assert Planalto.caminhos(NormaId("lei", 10833, None, "federal")) == []
    assert Planalto.caminhos(NormaId("mp", 2158, 2001, "federal")) == []


def test_aceita_so_federal_e_tipos_cobertos():
    assert not Planalto().aceita(NormaId("portaria", 1, 2020, "federal", "rfb"))
    assert not Planalto().aceita(NormaId("lei", 1, 2020, "df"))
    assert Planalto().aceita(LEI) and Lexml().aceita(LEI) and Camara().aceita(LEI)
    assert not Lexml().aceita(NormaId("dl", 406, 1968, "federal"))


def test_nao_encontrado_retorna_lista_vazia():
    rotas = {
        "https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2003;99999": (
            200,
            fx("lexml_naoencontrado.raw"),
            "text/html",
        ),
    }
    http, _, _ = montar(rotas)
    n = NormaId("lei", 99999, 2003, "federal")
    assert Planalto().localizar(n, http) == []  # tudo 404
    assert Lexml().localizar(n, http) == []  # 200 soft 404


def test_camara_busca_vazia_200():
    busca = (
        "https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal"
        "&geral=lei+99999"
    )
    http, _, _ = montar(
        {busca: (200, fx("camara_busca_naoencontrado.raw"), "text/html; charset=utf-8")}
    )
    assert Camara().localizar(NormaId("lei", 99999, 2003, "federal"), http) == []


def test_fonte_localiza_compilada_e_original():
    busca = (
        "https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal"
        "&geral=lei+10833"
    )
    norma = (
        "https://www2.camara.leg.br/legin/fed/lei/2003/"
        "lei-10833-29-dezembro-2003-497045-norma-pl.html"
    )
    http, pedidos, _ = montar(
        {
            busca: (200, fx("camara_busca_lei10833.raw"), "text/html; charset=utf-8"),
            norma: (200, fx("camara_lei_10833.raw"), "text/html; charset=utf-8"),
        }
    )
    c = Camara().localizar(LEI, http)
    base = "https://www2.camara.leg.br/legin/fed/lei/2003/lei-10833-29-dezembro-2003-497045-"
    assert {(x.visao, x.url) for x in c} == {
        ("compilada", base + "normaatualizada-pl.html"),
        ("original", base + "publicacaooriginal-1-pl.html"),
    }
    assert all(
        x.fonte == "camara" and x.situacao_fonte == "Não consta revogação expressa" for x in c
    )
    # decretos 5062/7455/10833 da busca por texto foram descartados por tipo/numero/ano
    assert not any("decreto" in p for p in pedidos if "legin" in p)


def test_camara_decreto_confere_numero_e_ano():
    busca = (
        "https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal"
        "&geral=decreto+70235"
    )
    norma = (
        "https://www2.camara.leg.br/legin/fed/decret/1970-1979/"
        "decreto-70235-6-marco-1972-418562-norma-pe.html"
    )
    http, _, _ = montar(
        {
            busca: (200, fx("camara_busca_decreto70235.raw"), "text/html; charset=utf-8"),
            norma: (200, fx("camara_decreto_70235.raw"), "text/html; charset=utf-8"),
        }
    )
    assert len(Camara().localizar(DEC, http)) >= 1
    # ano errado: nada
    http2, _, _ = montar(
        {busca: (200, fx("camara_busca_decreto70235.raw"), "text/html; charset=utf-8")}
    )
    assert Camara().localizar(NormaId("decreto", 70235, 1999, "federal"), http2) == []


def test_lexml_traz_links_da_camara_https():
    url = "https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2003;10833"
    http, _, _ = montar({url: (200, fx("lexml_urn_lei10833.raw"), "text/html; charset=utf-8")})
    c = Lexml().localizar(LEI, http)
    assert {x.visao for x in c} == {"original", "compilada"}
    assert all(x.url.startswith("https://www2.camara.leg.br/legin/fed/lei/2003/") for x in c)
    assert all(x.fonte == "lexml" and x.situacao_fonte is None for x in c)


def test_federais_ordem():
    assert [f.nome for f in FONTES_FEDERAIS] == ["planalto", "lexml", "camara"]


ROBOTS_LEX = "User-agent: *\nDisallow: /busca/\nAllow: /urn\n"


def test_robots_proibido_levanta_bloqueada_sem_baixar():
    http, pedidos, _ = montar(
        {"https://www.lexml.gov.br/robots.txt": (200, ROBOTS_LEX.encode(), "text/plain")}
    )
    with pytest.raises(Bloqueada):
        http.get("https://www.lexml.gov.br/busca/?q=x")
    assert [p for p in pedidos if "/busca/" in p] == []
    assert http.get("https://www.lexml.gov.br/urn/x").status_code == 404  # permitido
    assert pedidos.count("https://www.lexml.gov.br/robots.txt") == 1  # cache por host


def test_robots_html_ou_404_nao_bloqueia():
    spa = b"<!doctype html><html><body>app</body></html>"
    http, _, _ = montar(
        {"https://normas.receita.fazenda.gov.br/robots.txt": (200, spa, "text/html")}
    )
    assert http.get("https://normas.receita.fazenda.gov.br/x").status_code == 404


def test_403_levanta_bloqueada():
    http, _, _ = montar({PL + "leis/l1.htm": (403, b"no", "text/html")})
    with pytest.raises(Bloqueada):
        http.get(PL + "leis/l1.htm")


def test_429_recua_e_depois_bloqueia():
    n = {"c": 0}
    rel = Relogio()

    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        n["c"] += 1
        return httpx.Response(429 if n["c"] < 2 else 200, content=b"ok")

    http = Http(
        httpx.Client(transport=httpx.MockTransport(h)),
        atraso=1,
        relogio=rel.agora,
        dormir=rel.dormir,
    )
    assert http.get("https://x.test/a").status_code == 200 and 60.0 in rel.pausas
    http2 = Http(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 429)
            )
        ),
        atraso=1,
        relogio=rel.agora,
        dormir=rel.dormir,
    )
    with pytest.raises(Bloqueada):
        http2.get("https://x.test/a")


def test_limite_por_host():
    http, _, rel = montar(
        {}, atraso=1.0, atrasos={"www.camara.leg.br": 6.0, "www2.camara.leg.br": 40.0}
    )
    http.get("https://a.test/1")  # robots.txt + pedido: o segundo espera 1 s
    assert rel.pausas == [1.0]
    rel.pausas.clear()
    http.get("https://a.test/2")
    assert rel.pausas == [1.0]
    rel.pausas.clear()
    http.get(
        "https://www2.camara.leg.br/x"
    )  # paginas: limite proprio medido em 2026-11-06, separado da busca
    http.get("https://www.camara.leg.br/y")
    assert rel.pausas == [40.0, 6.0]


def _http_fn(h, atraso=0.0):
    rel = Relogio()
    return Http(
        httpx.Client(transport=httpx.MockTransport(h)),
        atraso=atraso,
        relogio=rel.agora,
        dormir=rel.dormir,
    ), rel


def test_5xx_tenta_de_novo_e_depois_indisponivel():
    n = {"c": 0}

    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        n["c"] += 1
        return httpx.Response(503)

    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get("https://x.test/a")
    assert n["c"] == 2
    # uma falha e sucesso na segunda: ok
    k = {"c": 0}

    def h2(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        k["c"] += 1
        return httpx.Response(500 if k["c"] == 1 else 200, content=b"ok")

    http2, _ = _http_fn(h2)
    assert http2.get("https://x.test/a").status_code == 200


def test_erro_de_rede_e_timeout_viram_indisponivel():
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.ConnectTimeout("lento")

    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get("https://x.test/a")


def test_localizar_propaga_indisponivel_e_nunca_devolve_vazio():
    def h(req):
        return httpx.Response(404 if req.url.path == "/robots.txt" else 502)

    http, _ = _http_fn(h)
    for f in (Planalto(), Lexml(), Camara()):
        with pytest.raises(Indisponivel):
            f.localizar(LEI, http)


def test_camara_busca_com_status_inesperado_e_indisponivel():
    busca = "https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal&geral=lei+10833"
    http, _, _ = montar({busca: (404, b"x", "text/html")})
    with pytest.raises(Indisponivel):
        Camara().localizar(LEI, http)


def test_lexml_status_inesperado_e_indisponivel():
    http, _, _ = montar(
        {"https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2003;10833": (500, b"", "text/html")}
    )
    with pytest.raises(Indisponivel):
        Lexml().localizar(LEI, http)


def test_robots_5xx_nega_e_nao_guarda_cache():
    n = {"robots": 0, "x": 0}

    def h(req):
        if req.url.path == "/robots.txt":
            n["robots"] += 1
            return httpx.Response(500 if n["robots"] <= 2 else 404)
        n["x"] += 1
        return httpx.Response(200, content=b"ok")

    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get("https://x.test/a")
    assert n["x"] == 0  # negado sem baixar
    assert http.get("https://x.test/a").status_code == 200  # nao ficou em cache
    assert n["robots"] == 3


def test_robots_401_403_bloqueia_e_guarda_sem_nova_requisicao():
    n = {"robots": 0, "x": 0}

    def h(req):
        if req.url.path == "/robots.txt":
            n["robots"] += 1
            return httpx.Response(403)
        n["x"] += 1
        return httpx.Response(200)

    http, _ = _http_fn(h)
    for _ in range(3):
        with pytest.raises(Bloqueada):
            http.get("https://x.test/a")
    assert n == {"robots": 1, "x": 0}


def test_robots_404_libera():
    http, pedidos, _ = montar({PL + "leis/l1.htm": (200, b"ok", "text/html")})
    assert http.get(PL + "leis/l1.htm").status_code == 200


def test_redirect_manual_segue_ate_5_saltos_com_atraso_e_robots_a_cada_um():
    rel = Relogio()
    visto = []

    def h(req):
        visto.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        n = int(req.url.path[1:])
        return (
            httpx.Response(301, headers={"location": f"/{n + 1}"})
            if n < 3
            else httpx.Response(200, content=b"fim")
        )

    http = Http(
        httpx.Client(transport=httpx.MockTransport(h)),
        atraso=2.0,
        relogio=rel.agora,
        dormir=rel.dormir,
    )
    assert http.get("https://x.test/1").content == b"fim"
    assert visto == ["/robots.txt", "/1", "/2", "/3"]
    assert rel.pausas == [2.0, 2.0, 2.0]  # atraso em cada salto (robots foi o primeiro pedido)


def test_redirect_para_caminho_proibido_levanta_bloqueada_sem_requisicao():
    visto = []

    def h(req):
        visto.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, content=b"User-agent: *\nDisallow: /privado/\n")
        return httpx.Response(302, headers={"location": "/privado/x"})

    http, _ = _http_fn(h)
    with pytest.raises(Bloqueada):
        http.get("https://x.test/a")
    assert "/privado/x" not in visto


def test_redirect_para_outro_host_respeita_robots_do_destino():
    visto = []

    def h(req):
        visto.append(str(req.url))
        if req.url.path == "/robots.txt" and req.url.host == "b.test":
            return httpx.Response(200, content=b"User-agent: *\nDisallow: /\n")
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(301, headers={"location": "https://b.test/z"})

    http, _ = _http_fn(h)
    with pytest.raises(Bloqueada):
        http.get("https://a.test/a")
    assert "https://b.test/z" not in visto


def test_redirect_excesso_de_saltos_e_indisponivel():
    def h(req):
        return (
            httpx.Response(404)
            if req.url.path == "/robots.txt"
            else httpx.Response(301, headers={"location": "/loop"})
        )

    http, _ = _http_fn(h)
    with pytest.raises(Indisponivel):
        http.get("https://x.test/loop")


def test_429_honra_retry_after_com_teto_300():
    def mk(valor):
        n = {"c": 0}

        def h(req):
            if req.url.path == "/robots.txt":
                return httpx.Response(404)
            n["c"] += 1
            return (
                httpx.Response(429, headers={"retry-after": valor})
                if n["c"] == 1
                else httpx.Response(200)
            )

        return h

    http, rel = _http_fn(mk("7"))
    assert (
        http.get("https://x.test/a").status_code == 200
        and 7.0 in rel.pausas
        and 60.0 not in rel.pausas
    )
    http, rel = _http_fn(mk("9999"))
    http.get("https://x.test/a")
    assert 300.0 in rel.pausas
    http, rel = _http_fn(mk("Wed, 21 Oct 2026 07:28:00 GMT"))  # data HTTP: usa o recuo padrao
    http.get("https://x.test/a")
    assert 60.0 in rel.pausas


# ---- Task 6: DF, CONFAZ, Receita ----
import json

from backend.crawler.fontes_normas import (
    FONTES_CONFAZ,
    FONTES_DF,
    FONTES_RFB,
    Ambigua,
    Candidato,
    Confaz,
    Receita,
    Sinj,
)

SINJ_BUSCA = (
    "https://www.sinj.df.gov.br/sinj/ashx/Datatable/ResultadoDePesquisaNormaDatatable.ashx?"
    "tipo_pesquisa=norma&nm_tipo_norma={t}&nr_norma={n}&ano_assinatura={a}&bbusca=sinj_norma"
    "&iDisplayStart=0&iDisplayLength=10&sEcho=1"
)
CONFAZ_IDX = "https://www.confaz.fazenda.gov.br/legislacao/"
RFB_BUSCA = "https://normas.receita.fazenda.gov.br/api/indexacao/ato/pesquisar"
JSON_CT = "application/json"


def rotas_sinj(t, n, a, fixture):
    return {SINJ_BUSCA.format(t=t, n=n, a=a): (200, fx(fixture), JSON_CT)}


def test_listas_por_jurisdicao():
    assert [f.nome for f in FONTES_DF] == ["sinj"]
    assert [f.nome for f in FONTES_CONFAZ] == ["confaz"]
    assert [f.nome for f in FONTES_RFB] == ["receita"]


def test_sinj_lei_df_devolve_texto_compilado_com_situacao():
    http, pedidos, _ = montar(rotas_sinj("Lei", 1254, 1996, "sinj_busca_lei1254_1996.raw"))
    norma = NormaId("lei", 1254, 1996, "df")
    assert Sinj().aceita(norma)
    assert Sinj().localizar(norma, http) == [
        Candidato(
            "https://www.sinj.df.gov.br/sinj/Norma/49208/Lei_1254.html",
            "sinj",
            "compilada",
            "Alterado",
        )
    ]


def test_sinj_nao_aceita_federal_nem_tipo_sem_equivalente():
    assert not Sinj().aceita(NormaId("lei", 10833, 2003, "federal"))
    assert not Sinj().aceita(NormaId("convenio_icms", 52, 2017, "df"))


def test_sinj_filtra_tipo_exato_e_nao_confunde_portaria_conjunta():
    http, _, _ = montar(rotas_sinj("Portaria", 42, 2016, "sinj_busca_portaria_42_2016.raw"))
    cands = Sinj().localizar(NormaId("portaria", 42, 2016, "df"), http)
    assert [c.url for c in cands] == [
        "https://www.sinj.df.gov.br/sinj/Norma/db70bab2d3844aaa836b1994bbac1a76/iprev_prt_42_2016.html"
    ]
    assert cands[0].situacao_fonte == "Revogado"


def test_sinj_mesmo_tipo_e_numero_duplicado_e_ambigua():
    d = json.loads(fx("sinj_busca_lei1254_1996.raw"))
    d["aaData"].append(json.loads(json.dumps(d["aaData"][0])))
    d["aaData"][1]["_source"]["ch_norma"] = "99999"
    rotas = {SINJ_BUSCA.format(t="Lei", n=1254, a=1996): (200, json.dumps(d).encode(), JSON_CT)}
    http, _, _ = montar(rotas)
    with pytest.raises(Ambigua) as e:
        Sinj().localizar(NormaId("lei", 1254, 1996, "df"), http)
    assert e.value.motivo


def test_sinj_lc_usa_nome_exato_e_ausente_devolve_vazio():
    http, pedidos, _ = montar(
        rotas_sinj("Lei+Complementar", 840, 2011, "sinj_busca_lc_840_2011.raw")
    )
    assert len(Sinj().localizar(NormaId("lc", 840, 2011, "df"), http)) == 1
    http, _, _ = montar(rotas_sinj("Lei", 9, 1999, "sinj_busca_naoencontrado.raw"))
    assert Sinj().localizar(NormaId("lei", 9, 1999, "df"), http) == []


def test_sinj_5xx_e_indisponivel_nunca_vazio():
    http, _, _ = montar({SINJ_BUSCA.format(t="Lei", n=1254, a=1996): (503, b"", "text/html")})
    with pytest.raises(Indisponivel):
        Sinj().localizar(NormaId("lei", 1254, 1996, "df"), http)


def test_confaz_convenio_pelo_span_do_indice_anual():
    rotas = {
        CONFAZ_IDX + "convenios/2017": (
            200,
            fx("confaz_indice_convenios_2017.raw"),
            "text/html; charset=utf-8",
        )
    }
    http, _, _ = montar(rotas)
    norma = NormaId("convenio_icms", 52, 2017, "confaz")
    assert Confaz().aceita(norma) and not Confaz().aceita(NormaId("lei", 1, 2017, "federal"))
    assert Confaz().localizar(norma, http) == [
        Candidato(CONFAZ_IDX + "convenios/2017/CV052_17", "confaz", "unica")
    ]
    assert Confaz().localizar(NormaId("convenio_icms", 9999, 2017, "confaz"), http) == []


def test_confaz_ajuste_ignora_anterior_e_404_do_indice_e_nao_encontrada():
    rotas = {
        CONFAZ_IDX + "ajustes/2005": (
            200,
            fx("confaz_indice_ajustes_2005.raw"),
            "text/html; charset=utf-8",
        )
    }
    http, _, _ = montar(rotas)
    cands = Confaz().localizar(NormaId("ajuste_sinief", 7, 2005, "confaz"), http)
    assert [c.url for c in cands] == [CONFAZ_IDX + "ajustes/2005/AJ007_05"]
    assert Confaz().localizar(NormaId("ajuste_sinief", 7, 2006, "confaz"), http) == []  # 404 real


def rotas_rfb(fixture):
    return {RFB_BUSCA: (200, fx(fixture), JSON_CT)}


def test_receita_portaria_devolve_visoes_multivigente_e_original_com_situacao():
    http, _, _ = montar(rotas_rfb("receita_busca_sem_tipo_1750_2018.raw"))
    norma = NormaId("portaria", 1750, 2018, "federal", "rfb")
    base = "https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/96434/visao/"
    assert Receita().aceita(norma) and not Receita().aceita(NormaId("lei", 1, 2018, "federal"))
    assert Receita().localizar(norma, http) == [
        Candidato(base + "multivigente", "receita", "compilada", "Vigente"),
        Candidato(base + "original", "receita", "original", "Vigente"),
    ]


def test_receita_envia_numero_e_ano_sem_tipo_e_pagina():
    corpos = []
    http, _, _ = montar(rotas_rfb("receita_busca_naoencontrado.raw"), corpos=corpos)
    assert Receita().localizar(NormaId("in", 1, 2018, "federal", "rfb"), http) == []
    c = json.loads(corpos[0])
    assert (c["numeroAto"], c["anoAto"], c["tiposAtosSelecionados"], c["paginacaoPaginaAtual"]) == (
        "1",
        "2018",
        "",
        1,
    )


def test_receita_orgao_none_com_varios_orgaos_e_ambigua_e_com_orgao_filtra():
    http, _, _ = montar(rotas_rfb("receita_busca_sem_tipo_140_2018.raw"))
    with pytest.raises(Ambigua) as e:
        Receita().localizar(NormaId("portaria", 140, 2018, "federal"), http)
    assert "orgao" in e.value.motivo
    cands = Receita().localizar(NormaId("portaria", 140, 2018, "federal", "drf/rj1"), http)
    assert [c.url.split("/ato/")[1].split("/")[0] for c in cands] == ["96337", "96337"]


def test_receita_idato_repetido_vira_um_candidato_so():
    d = json.loads(fx("receita_busca_sem_tipo_1750_2018.raw"))
    d["atos"].append(d["atos"][0])
    http, _, _ = montar({RFB_BUSCA: (200, json.dumps(d).encode(), JSON_CT)})
    assert (
        len(Receita().localizar(NormaId("portaria", 1750, 2018, "federal"), http)) == 2
    )  # multivigente + original


def test_receita_percorre_todas_as_paginas():
    p1 = json.loads(fx("receita_busca_sem_tipo_1_2018.raw"))
    p2 = json.loads(fx("receita_busca_sem_tipo_1750_2018.raw"))
    p2["atos"][0]["numeroAto"] = "1"
    p2["atos"][0]["anoAto"] = "2018"
    p1["quantidadePaginas"] = 2
    p2["quantidadePaginas"] = 2
    paginas = []

    def handler(req):
        if req.method == "GET":  # robots.txt
            return httpx.Response(404)
        c = json.loads(req.content)
        paginas.append(c["paginacaoPaginaAtual"])
        return httpx.Response(
            200,
            content=json.dumps(p1 if c["paginacaoPaginaAtual"] == 1 else p2).encode(),
            headers={"content-type": JSON_CT},
        )

    http = Http(
        httpx.Client(transport=httpx.MockTransport(handler)),
        atraso=0.0,
        relogio=Relogio().agora,
        dormir=lambda s: None,
    )
    # pagina 1 tem a Portaria Conjunta PGFN/RFB (tipo aceito) e a pagina 2 a Portaria RFB: 2 atos, 2 visoes cada
    with pytest.raises(Ambigua):
        Receita().localizar(NormaId("portaria", 1, 2018, "federal"), http)
    assert paginas == [1, 2]


def test_receita_5xx_e_indisponivel():
    http, _, _ = montar({RFB_BUSCA: (500, b"", "text/html")})
    with pytest.raises(Indisponivel):
        Receita().localizar(NormaId("portaria", 1750, 2018, "federal"), http)


def test_http_post_respeita_robots_e_bloqueio():
    http, pedidos, _ = montar(
        {
            "https://normas.receita.fazenda.gov.br/robots.txt": (
                200,
                b"User-agent: *\nDisallow: /api/\n",
                "text/plain",
            )
        }
    )
    with pytest.raises(Bloqueada):
        http.post(RFB_BUSCA, {"a": 1})
    assert pedidos == ["https://normas.receita.fazenda.gov.br/robots.txt"]


def test_sinj_registro_sem_texto_compilado_levanta_sem_texto_automatico():
    from backend.crawler.fontes_normas import SemTextoAutomatico

    d = json.loads(fx("sinj_busca_lei1254_1996.raw"))
    d["aaData"][0]["_source"]["ar_atualizado"] = None
    http, _, _ = montar(
        {SINJ_BUSCA.format(t="Lei", n=1254, a=1996): (200, json.dumps(d).encode(), JSON_CT)}
    )
    with pytest.raises(SemTextoAutomatico) as e:
        Sinj().localizar(NormaId("lei", 1254, 1996, "df"), http)
    assert e.value.motivo


def test_atraso_por_host_vale_entre_threads():
    """Duas threads no mesmo host nunca pedem juntas; o atraso minimo separa as requisicoes."""
    import threading

    relogio = threading.Lock()
    estado = {"t": 1000.0}
    chegadas, barreira = [], threading.Barrier(2)

    def agora():
        return estado["t"]

    def dormir(s):
        with relogio:
            estado["t"] += s

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        chegadas.append(agora())
        try:
            barreira.wait(timeout=0.5)  # sem trava por host as duas threads chegam aqui juntas
        except threading.BrokenBarrierError:
            pass
        return httpx.Response(200, content=b"ok")

    http = Http(
        httpx.Client(transport=httpx.MockTransport(handler)),
        atraso=2.0,
        relogio=agora,
        dormir=dormir,
    )
    ts = [threading.Thread(target=http.get, args=(f"https://a.gov.br/{i}",)) for i in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(chegadas) == 2 and abs(chegadas[1] - chegadas[0]) >= 2.0


# ---- Task 8a: Constituicao, EC, LODF, sem ano, varios idAto ----

CAM_BUSCA = (
    "https://www.camara.leg.br/legislacao/busca?abrangencia=Legisla%C3%A7%C3%A3o+Federal&geral="
)
SINJ_SEM_ANO = (
    "https://www.sinj.df.gov.br/sinj/ashx/Datatable/ResultadoDePesquisaNormaDatatable.ashx?"
    "tipo_pesquisa=norma&nm_tipo_norma={t}&nr_norma={n}&bbusca=sinj_norma"
    "&iDisplayStart=0&iDisplayLength=100&sEcho=1"
)
SINJ_LODF = (
    "https://www.sinj.df.gov.br/sinj/ashx/Datatable/ResultadoDePesquisaNormaDatatable.ashx?"
    "tipo_pesquisa=norma&nm_tipo_norma=Lei+Org%C3%A2nica&nr_norma=0&ano_assinatura=1993&bbusca=sinj_norma"
    "&iDisplayStart=0&iDisplayLength=200&sEcho=1"
)
CF = NormaId("constituicao", 0, 1988, "federal")
LODF = NormaId("lodf", 0, 1993, "df")


def test_planalto_constituicao_e_emenda():
    assert Planalto.caminhos(CF) == ["constituicao/constituicao.htm"]
    assert Planalto.caminhos(NormaId("ec", 132, 2023, "federal")) == [
        "constituicao/emendas/emc/emc132.htm"
    ]
    assert Planalto.caminhos(NormaId("ec", 5, 1995, "federal")) == [
        "constituicao/emendas/emc/emc05.htm"
    ]
    assert (
        Planalto.caminhos(NormaId("ec", 1, 1969, "federal")) == []
    )  # anterior a CF/88: URL nao verificada
    assert Planalto.caminhos(NormaId("ec", 132, None, "federal")) == []
    assert Planalto().aceita(CF) and Planalto().aceita(NormaId("ec", 132, 2023, "federal"))


def test_planalto_localiza_emenda_e_constituicao():
    http, pedidos, _ = montar(
        {
            PL + "constituicao/emendas/emc/emc132.htm": (
                200,
                fx("planalto_emc_132.raw"),
                "text/html",
            ),
            PL + "constituicao/constituicao.htm": (
                200,
                fx("planalto_constituicao.raw"),
                "text/html",
            ),
        }
    )
    assert (
        Planalto()
        .localizar(NormaId("ec", 132, 2023, "federal"), http)[0]
        .url.endswith("emc/emc132.htm")
    )
    assert Planalto().localizar(CF, http)[0].url.endswith("constituicao/constituicao.htm")


def test_camara_reserva_para_constituicao_e_emenda():
    cb = fx("camara_busca_constituicao.raw")
    pagina = "https://www2.camara.leg.br/legin/fed/consti/1988/constituicao-1988-5-outubro-1988-322142-norma-pl.html"
    corpo = b'<a href="constituicao-1988-5-outubro-1988-322142-normaatualizada-pl.html">x</a>'
    http, _, _ = montar(
        {
            CAM_BUSCA + "constitui%C3%A7%C3%A3o+federal+1988": (
                200,
                cb,
                "text/html; charset=utf-8",
            ),
            pagina: (200, corpo, "text/html"),
        }
    )
    c = Camara().localizar(CF, http)
    assert [x.url for x in c] == [pagina.replace("-norma-", "-normaatualizada-")]
    http, _, _ = montar(
        {
            CAM_BUSCA + "emenda+constitucional+132": (
                200,
                fx("camara_busca_ec132.raw"),
                "text/html; charset=utf-8",
            )
        }
    )
    assert Camara().localizar(NormaId("ec", 132, 2024, "federal"), http) == []  # ano errado
    assert Camara().aceita(NormaId("ec", 132, 2023, "federal")) and not Camara().aceita(
        NormaId("ec", 132, None, "federal")
    )


def test_sinj_lei_organica_do_df_pela_busca_sem_numero():
    http, pedidos, _ = montar({SINJ_LODF: (200, fx("sinj_busca_lodf_1993.raw"), JSON_CT)})
    assert Sinj().aceita(LODF)
    c = Sinj().localizar(LODF, http)
    assert [x.url for x in c] == ["https://www.sinj.df.gov.br/sinj/Norma/66634/LODF.html"]
    assert c[0].situacao_fonte == "Alterado"


def test_sinj_lodf_ausente_ou_duplicada():
    d = json.loads(fx("sinj_busca_lodf_1993.raw"))
    sem = dict(
        d,
        aaData=[ln for ln in d["aaData"] if ln["_source"]["nm_tipo_norma"] != "Lei Orgânica"],
        iTotalDisplayRecords=2,
    )
    http, _, _ = montar({SINJ_LODF: (200, json.dumps(sem).encode(), JSON_CT)})
    assert Sinj().localizar(LODF, http) == []
    dup = dict(d, aaData=d["aaData"] + [d["aaData"][0]], iTotalDisplayRecords=4)
    http, _, _ = montar({SINJ_LODF: (200, json.dumps(dup).encode(), JSON_CT)})
    with pytest.raises(Ambigua):
        Sinj().localizar(LODF, http)


def test_camara_sem_ano_aceita_so_um_resultado():
    n = NormaId("lei", 10833, None, "federal")
    assert Camara().aceita(n) and not Planalto().aceita(n)
    assert not Camara().aceita(NormaId("mp", 10, None, "federal"))
    assert not Camara().aceita(NormaId("portaria", 10, None, "federal", "rfb"))
    norma = "https://www2.camara.leg.br/legin/fed/lei/2003/lei-10833-29-dezembro-2003-497045-norma-pl.html"
    http, _, _ = montar(
        {
            CAM_BUSCA + "lei+10833": (
                200,
                fx("camara_busca_lei10833.raw"),
                "text/html; charset=utf-8",
            ),
            norma: (200, fx("camara_lei_10833.raw"), "text/html; charset=utf-8"),
        }
    )
    assert len(Camara().localizar(n, http)) == 2


def test_camara_sem_ano_varios_resultados_ou_pagina_incompleta_e_ambigua():
    n = NormaId("lei", 10833, None, "federal")
    b = fx("camara_busca_lei10833.raw").decode("utf-8")
    href = "https://www2.camara.leg.br/legin/fed/lei/2003/lei-10833-29-dezembro-2003-497045-norma-pl.html"
    outra = href.replace("2003", "2010").replace("497045", "111111")
    dupla = b.replace(href, href + '"></a><a href="' + outra, 1)
    http, _, _ = montar(
        {CAM_BUSCA + "lei+10833": (200, dupla.encode(), "text/html; charset=utf-8")}
    )
    with pytest.raises(Ambigua):
        Camara().localizar(n, http)
    mais = b.replace("de 1 a 5 de 5", "de 1 a 5 de 60")
    http, _, _ = montar({CAM_BUSCA + "lei+10833": (200, mais.encode(), "text/html; charset=utf-8")})
    with pytest.raises(Ambigua):
        Camara().localizar(n, http)


def test_sinj_sem_ano_so_lei_lc_decreto_e_so_registro_unico():
    assert Sinj().aceita(NormaId("lei", 1254, None, "df")) and Sinj().aceita(
        NormaId("decreto", 1, None, "df")
    )
    assert not Sinj().aceita(NormaId("portaria", 42, None, "df")) and not Sinj().aceita(
        NormaId("in", 1, None, "df")
    )
    http, _, _ = montar(
        {SINJ_SEM_ANO.format(t="Lei", n=1254): (200, fx("sinj_busca_lei1254_sem_ano.raw"), JSON_CT)}
    )
    c = Sinj().localizar(NormaId("lei", 1254, None, "df"), http)
    assert [x.url for x in c] == ["https://www.sinj.df.gov.br/sinj/Norma/49208/Lei_1254.html"]
    d = json.loads(fx("sinj_busca_lc840_sem_ano.raw"))
    d["iTotalDisplayRecords"] = len(d["aaData"]) + 2  # pagina incompleta: unicidade nao verificavel
    http, _, _ = montar(
        {SINJ_SEM_ANO.format(t="Lei+Complementar", n=840): (200, json.dumps(d).encode(), JSON_CT)}
    )
    with pytest.raises(Ambigua, match="mais resultados"):
        Sinj().localizar(NormaId("lc", 840, None, "df"), http)


def test_sinj_sem_ano_dois_registros_do_mesmo_tipo_e_ambigua():
    d = json.loads(fx("sinj_busca_lei1254_sem_ano.raw"))
    lei = next(ln for ln in d["aaData"] if ln["_source"]["nm_tipo_norma"] == "Lei")
    outra = json.loads(json.dumps(lei))
    outra["_source"].update(ch_norma="999", dt_assinatura="01/01/2001")
    d["aaData"].append(outra)
    d["iTotalDisplayRecords"] = len(d["aaData"])
    http, _, _ = montar(
        {SINJ_SEM_ANO.format(t="Lei", n=1254): (200, json.dumps(d).encode(), JSON_CT)}
    )
    with pytest.raises(Ambigua):
        Sinj().localizar(NormaId("lei", 1254, None, "df"), http)


def test_receita_varios_idato_mesmo_orgao_devolve_todos_os_candidatos():
    http, _, _ = montar(rotas_rfb("receita_busca_sem_tipo_140_2018.raw"))
    cands = Receita().localizar(NormaId("resol_cgsn", 140, 2018, "federal"), http)
    assert {c.url.split("/ato/")[1].split("/")[0] for c in cands} == {"116138", "92278", "114000"}
    assert len(cands) == 6
    http, _, _ = montar(rotas_rfb("receita_busca_in971_revogada.raw"))
    assert len(Receita().localizar(NormaId("in", 971, 2009, "federal", "rfb"), http)) == 4


def test_camara_sem_ano_pagina_truncada_e_ambigua_mesmo_sem_acerto_e_sem_contagem():
    n = NormaId("lei", 99999, None, "federal")
    b = fx("camara_busca_naoencontrado.raw").decode("utf-8")
    url = CAM_BUSCA + "lei+99999"
    http, _, _ = montar(
        {
            url: (
                200,
                b.replace("de 0 a 0 de 0", "de 1 a 20 de 300").encode(),
                "text/html; charset=utf-8",
            )
        }
    )
    with pytest.raises(
        Ambigua
    ):  # nenhum acerto na pagina 1, mas ha mais paginas: nunca nao_encontrada
        Camara().localizar(n, http)
    http, _, _ = montar(
        {
            url: (
                200,
                b.replace("Exibindo resultados", "Mostrando").encode(),
                "text/html; charset=utf-8",
            )
        }
    )
    with pytest.raises(Ambigua):  # sem contagem de resultados nao ha como provar unicidade
        Camara().localizar(n, http)
    http, _, _ = montar({url: (200, b.encode(), "text/html; charset=utf-8")})
    assert Camara().localizar(n, http) == []  # 0 de 0 e ausencia verdadeira


def test_sinj_sem_ano_sem_total_de_registros_e_indisponivel():
    d = json.loads(fx("sinj_busca_lei1254_sem_ano.raw"))
    del d["iTotalDisplayRecords"]
    http, _, _ = montar(
        {SINJ_SEM_ANO.format(t="Lei", n=1254): (200, json.dumps(d).encode(), JSON_CT)}
    )
    with pytest.raises(Indisponivel):
        Sinj().localizar(NormaId("lei", 1254, None, "df"), http)


def test_429_tem_teto_e_o_atraso_volta_ao_normal():
    """Bug real: cada 429 dobrava o atraso da Camara para sempre (6 s virou 384 s)."""
    respostas = iter([429, 200] * 8 + [200] * 40)

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(next(respostas), headers={"Retry-After": "1"})

    rel = Relogio()
    http = Http(
        httpx.Client(transport=httpx.MockTransport(handler)),
        atrasos={"x.gov.br": 6.0},
        relogio=rel.agora,
        dormir=rel.dormir,
    )
    for i in range(8):
        http.get(f"https://x.gov.br/{i}")
        assert http.atrasos["x.gov.br"] <= 30.0
    for i in range(40):
        http.get(f"https://x.gov.br/ok{i}")
    assert http.atrasos["x.gov.br"] == 6.0
