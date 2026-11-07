import json
from pathlib import Path

import pytest

from backend.crawler.catalogo import Hasher, audit_snapshot
from backend.crawler.fontes_normas import Candidato
from backend.crawler.normas_id import NormaId
from backend.crawler.normas_ingest import (
    chave_segura,
    identificar_cabecalho,
    ingerir,
    resolver_assunto,
    validar_identidade,
)

FIX = Path(__file__).parent / "fixtures" / "normas"
LEI = NormaId("lei", 10833, 2003, "federal")
PLAN = Candidato(
    "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2003/lei/l10.833.htm", "planalto", "unica"
)


def fx(nome: str) -> bytes:
    return (FIX / nome).read_bytes()


def html(corpo: str, titulo="L10833") -> bytes:
    return f"<html><head><title>{titulo}</title></head><body>{corpo}</body></html>".encode("utf-8")


def lei_html(extra="") -> bytes:
    return html(
        "<p>LEI N<sup>o</sup> 10.833, DE 29 DE DEZEMBRO DE 2003.</p><p>Altera a Legislação Tributária.</p>"
        "<p>Art. 1<sup>o</sup> Texto do artigo.</p>" + extra
    )


def pdf_bytes(texto: str | None) -> bytes:
    """PDF minimo valido de uma pagina; texto None = pagina sem texto (digitalizada)."""
    conteudo = b"" if texto is None else f"BT /F1 12 Tf 50 150 Td ({texto}) Tj ET".encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1,
        xref,
    )


# ---- validar_identidade ----


@pytest.mark.parametrize(
    "cabecalho",
    [
        "LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003.",
        "Lei nº 10833, de 29 de dezembro de 2003",
        "LEI N o 10.833, DE 29 DE DEZEMBRO DE 2003.",
        "Lei n° 10.833, de 29/12/2003",
        "Presidência da República Casa Civil LEI N º 10.833/2003",
    ],
)
def test_grafias_do_cabecalho_passam(cabecalho):
    assert validar_identidade(LEI, cabecalho + " Altera a legislação. Art. 1º Fica instituído.")


def test_numero_ou_ano_diferente_e_rejeitado():
    lei_2002 = "LEI Nº 10.637, DE 30 DE DEZEMBRO DE 2002. Dispõe sobre a COFINS. Art. 1º Texto."
    assert not validar_identidade(LEI, lei_2002)
    assert not validar_identidade(
        NormaId("lei", 10833, 2004, "federal"),
        "LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003. Art. 1º X",
    )
    assert not validar_identidade(LEI, "LEI Nº 1.083, DE 29 DE DEZEMBRO DE 2003. Art. 1º X")


def test_tipo_diferente_e_rejeitado():
    lc = "LEI COMPLEMENTAR Nº 214, DE 16 DE JANEIRO DE 2025. Art. 1º Institui o IBS."
    assert validar_identidade(NormaId("lc", 214, 2025, "federal"), lc)
    assert not validar_identidade(NormaId("lei", 214, 2025, "federal"), lc)
    assert not validar_identidade(NormaId("decreto", 214, 2025, "federal"), lc)


@pytest.mark.parametrize(
    "abertura",
    [
        "# Solução de Consulta Cosit nº 112, de 12 de junho de 2023",
        "Declaração de Ineficácia 19/2023",
        "TARF — Acórdão 93/2023",
        "Acórdão nº 12/2020",
        "Parecer nº 3/2019",
    ],
)
def test_documento_de_outro_tipo_que_cita_a_norma_nao_passa(abertura):
    for citacao in (
        "LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003",
        "Lei nº 10.833, de 29 de dezembro de 2003",
    ):
        texto = "\n".join((abertura, "Fundamentação legal:", citacao, "Texto."))
        assert identificar_cabecalho(texto) is None
        assert not validar_identidade(LEI, texto)


def test_caixa_mista_so_vale_perto_do_inicio():
    relato = ["Relata a consulente que tributa suas receitas conforme a legislação."] * 4
    citacao = "Lei nº 10.833, de 29 de dezembro de 2003, com alterações."
    assert not validar_identidade(LEI, "\n".join([*relato, citacao, "Texto."]))
    assert validar_identidade(
        LEI, "\n".join(["Presidência da República", "Casa Civil", citacao, "Art. 1º X"])
    )


def test_lei_que_apenas_cita_outra_no_preambulo_nao_passa():
    texto = (
        "LEI Nº 10.637, DE 30 DE DEZEMBRO DE 2002. Altera a Lei nº 9.718, de 27 de novembro de 1998, e dá outras "
        "providências. Art. 1º Texto."
    )
    assert not validar_identidade(NormaId("lei", 9718, 1998, "federal"), texto)
    sem_epigrafe = (
        "Altera a Lei nº 9.718, de 27 de novembro de 1998, e dá outras providências. Art. 1º Texto."
    )
    assert not validar_identidade(NormaId("lei", 9718, 1998, "federal"), sem_epigrafe)
    assert not validar_identidade(
        NormaId("lei", 9718, 1998, "federal"),
        "Vide Lei nº 9.718, de 27 de novembro de 1998. Art. 1º X",
    )


def test_sem_ano_na_norma_basta_numero_e_tipo_e_o_ano_vem_do_cabecalho():
    texto = (
        "LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003. Altera. Art. 1º Texto. Art. 2º Conforme a Lei nº 10.833, "
        "de 5 de maio de 2009."
    )
    semano = NormaId("lei", 10833, None, "federal")
    assert validar_identidade(semano, texto)
    assert identificar_cabecalho(texto) == ("lei", 10833, 2003, None)
    assert not validar_identidade(NormaId("lei", 10832, None, "federal"), texto)


def test_ano_do_corpo_nao_vale_se_o_cabecalho_nao_traz():
    texto = (
        "LEI Nº 10.833. Altera. Art. 1º Texto. Art. 2º Lei nº 10.833, de 29 de dezembro de 2003."
    )
    assert not validar_identidade(LEI, texto)
    assert identificar_cabecalho(texto) is None


def test_orgao_do_cabecalho_precisa_bater():
    texto = "Portaria RFB nº 1750, de 12 de novembro de 2018"
    assert validar_identidade(NormaId("portaria", 1750, 2018, "federal", "rfb"), texto)
    assert validar_identidade(NormaId("portaria", 1750, 2018, "federal"), texto)
    assert not validar_identidade(NormaId("portaria", 1750, 2018, "federal", "pgfn"), texto)


def test_convenio_com_ano_de_dois_digitos():
    assert validar_identidade(
        NormaId("convenio_icms", 52, 2017, "confaz"), "CONVÊNIO ICMS 52/17 — Conselho Nacional"
    )
    assert not validar_identidade(
        NormaId("convenio_icms", 52, 2017, "confaz"), "CONVÊNIO ICMS 52/18 — Conselho"
    )


# ---- ingerir: identidade, jurisdicao, soft 404 ----


def test_lei_df_nao_serve_para_federal_de_mesmo_numero(tmp_path):
    sinj = Candidato(
        "https://www.sinj.df.gov.br/sinj/Norma/49208/Lei_1254.html", "sinj", "compilada"
    )
    with pytest.raises(ValueError, match="jurisdi"):
        ingerir(
            NormaId("lei", 1254, 1996, "federal"),
            sinj,
            fx("sinj_lei_1254_atualizada.raw"),
            tmp_path,
        )
    with pytest.raises(ValueError, match="jurisdi"):
        ingerir(NormaId("lei", 10833, 2003, "df"), PLAN, fx("planalto_lei_10833.raw"), tmp_path)
    assert not (tmp_path / "normas-citadas").exists()


def test_numero_ou_ano_diferente_nao_grava(tmp_path):
    with pytest.raises(ValueError, match="identidade"):
        ingerir(
            NormaId("lei", 10637, 2002, "federal"), PLAN, fx("planalto_lei_10833.raw"), tmp_path
        )
    assert not (tmp_path / "normas-citadas").exists()


@pytest.mark.parametrize(
    "fonte,fixture,norma",
    [
        ("sinj", "sinj_soft404.raw", NormaId("lei", 9999, 1996, "df")),
        ("planalto", "planalto_naoencontrado.raw", LEI),
        ("lexml", "lexml_naoencontrado.raw", LEI),
        ("camara", "camara_norma_naoencontrada.raw", LEI),
        ("confaz", "confaz_naoencontrado.raw", NormaId("convenio_icms", 52, 2017, "confaz")),
    ],
)
def test_soft_404_e_redirecionamento_nao_coletam(tmp_path, fonte, fixture, norma):
    with pytest.raises(ValueError):
        ingerir(norma, Candidato("https://x.gov.br/a", fonte, "unica"), fx(fixture), tmp_path)
    home = html("<h1>Portal</h1><p>Bem-vindo. Página não encontrada. Lei 10.833.</p>", "Home")
    with pytest.raises(ValueError):
        ingerir(LEI, PLAN, home, tmp_path)
    assert not (tmp_path / "normas-citadas").exists()


def test_pdf_ou_json_invalidos_nao_coletam(tmp_path):
    from backend.crawler.normas_ingest import (
        ErroConversao,  # leitura impossivel = erro de conversao (termina manual)
    )

    with pytest.raises(ErroConversao):
        ingerir(LEI, Candidato("https://x/a.pdf", "planalto", "unica"), b"%PDF-1.4 lixo", tmp_path)
    rec = Candidato(
        "https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/1/visao/multivigente",
        "receita",
        "compilada",
    )
    with pytest.raises(ErroConversao):
        ingerir(NormaId("portaria", 1750, 2018, "federal"), rec, b"<html>erro</html>", tmp_path)
    assert not (tmp_path / "normas-citadas").exists()


# ---- ingerir: gravacao ----


def test_ingere_fixtures_de_cada_fonte(tmp_path):
    casos = [
        (LEI, PLAN, "planalto_lei_10833.raw", "original.html"),
        (
            NormaId("decreto", 70235, 1972, "federal"),
            Candidato(
                "https://www.planalto.gov.br/ccivil_03/decreto/d70235cons.htm",
                "planalto",
                "compilada",
            ),
            "planalto_decreto_70235.raw",
            "original.html",
        ),
        (
            LEI,
            Candidato(
                "https://www2.camara.leg.br/legin/fed/lei/2003/lei-10833-29-dezembro-2003-497045-publicacaooriginal-1-pl.html",
                "lexml",
                "original",
            ),
            "camara_lei_10833_original.raw",
            "original.html",
        ),
        (
            NormaId("lei", 1254, 1996, "df"),
            Candidato(
                "https://www.sinj.df.gov.br/sinj/Norma/49208/Lei_1254.html",
                "sinj",
                "compilada",
                "Alterado",
            ),
            "sinj_lei_1254_atualizada.raw",
            "original.html",
        ),
        (
            NormaId("convenio_icms", 52, 2017, "confaz"),
            Candidato(
                "https://www.confaz.fazenda.gov.br/legislacao/convenios/2017/CV052_17",
                "confaz",
                "unica",
            ),
            "confaz_convenio_52_17.raw",
            "original.html",
        ),
        (
            NormaId("portaria", 1750, 2018, "federal", "rfb"),
            Candidato(
                "https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/96434/visao/multivigente",
                "receita",
                "compilada",
                "Vigente",
            ),
            "receita_detalhe_96434.raw",
            "original.json",
        ),
    ]
    for norma, cand, fixture, original in casos:
        pasta = ingerir(norma, cand, fx(fixture), tmp_path)
        meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
        assert (pasta / original).read_bytes() == fx(fixture)
        assert (pasta / "documento.md").read_text(encoding="utf-8").strip()
        assert meta["norma_chave"] == norma.chave and meta["fonte"] == cand.fonte
        assert meta["visao_fonte"] == cand.visao and meta["situacao_fonte"] == cand.situacao_fonte
        assert meta["status"] == "coletado" and meta["original"] == original
        assert pasta.name == meta["sha256"] and pasta.parent.parent == tmp_path / "normas-citadas"


def test_metadados_campos_do_contrato(tmp_path):
    pasta = ingerir(LEI, PLAN, lei_html(), tmp_path, rodada=2)
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    for campo in (
        "source_url",
        "source_id",
        "titulo",
        "sha256",
        "markdown_sha256",
        "markdown_arquivo",
        "original",
        "coletado_em",
        "status",
        "visao_fonte",
        "natureza_documental",
        "vigencia",
        "jurisdicao",
        "norma_chave",
        "situacao_fonte",
        "fonte",
        "rodada",
    ):
        assert campo in meta, campo
    assert meta["natureza_documental"] == "legislacao" and meta["vigencia"] == "nao_verificada"
    assert (
        meta["jurisdicao"] == "federal" and meta["rodada"] == 2 and meta["source_url"] == PLAN.url
    )
    assert meta["markdown_arquivo"] == "documento.md" and meta["ano"] == 2003


def test_sem_ano_na_norma_o_ano_do_cabecalho_vai_para_os_metadados(tmp_path):
    pasta = ingerir(NormaId("lei", 10833, None, "federal"), PLAN, lei_html(), tmp_path)
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    assert meta["ano"] == 2003 and meta["norma_chave"] == "federal:lei:-:10833:?"


def test_ingest_idempotente_e_preserva_versao_anterior(tmp_path):
    v1 = lei_html()
    p1 = ingerir(LEI, PLAN, v1, tmp_path)
    antes = {f.name: (f.read_bytes(), f.stat().st_mtime_ns) for f in p1.iterdir()}
    assert ingerir(LEI, PLAN, v1, tmp_path) == p1
    assert {f.name: (f.read_bytes(), f.stat().st_mtime_ns) for f in p1.iterdir()} == antes
    v2 = lei_html("<p>Art. 2<sup>o</sup> Novo artigo.</p>")
    p2 = ingerir(LEI, PLAN, v2, tmp_path)
    assert p2 != p1 and p2.parent == p1.parent
    assert (p1 / "original.html").read_bytes() == v1 and (p2 / "original.html").read_bytes() == v2
    assert {f.name: (f.read_bytes(), f.stat().st_mtime_ns) for f in p1.iterdir()} == antes
    assert sorted(d.name for d in p1.parent.iterdir()) == sorted(
        [p1.name, p2.name]
    )  # sem .coleta- sobrando


def test_versao_existente_divergente_ou_incompleta_e_erro_sem_sobrescrever(tmp_path):
    pasta = ingerir(LEI, PLAN, lei_html(), tmp_path)
    (pasta / "documento.md").unlink()
    with pytest.raises(ValueError, match="incompleta"):
        ingerir(LEI, PLAN, lei_html(), tmp_path)
    assert not (pasta / "documento.md").exists()


def test_rasuras_tabelas_e_valores_sobrevivem(tmp_path):
    corpo = (
        "<p>Art. 2<sup>o</sup> <strike>Antigo</strike> <del>Outro</del> <s>Mais</s> vale R$ 1.000,00.</p>"
        "<table><tr><th>Faixa</th><th>Alíquota</th></tr><tr><td>até 180.000,00</td><td>4,00%</td></tr></table>"
        "<p>Vigência a partir de 01/01/2004.</p>"
    )
    pasta = ingerir(LEI, PLAN, lei_html(corpo), tmp_path)
    md = (pasta / "documento.md").read_text(encoding="utf-8")
    assert "~~Antigo~~" in md and "~~Outro~~" in md and "~~Mais~~" in md
    assert "R$ 1.000,00" in md and "01/01/2004" in md
    assert "| Faixa | Alíquota |" in md and "| até 180.000,00 | 4,00% |" in md


def test_receita_segmento_tachado_e_sinalizado(tmp_path):
    cand = Candidato(
        "https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/96434/visao/multivigente",
        "receita",
        "compilada",
    )
    pasta = ingerir(
        NormaId("portaria", 1750, 2018, "federal", "rfb"),
        cand,
        fx("receita_detalhe_96434.raw"),
        tmp_path,
    )
    md = (pasta / "documento.md").read_text(encoding="utf-8")
    assert (
        "Portaria RFB nº 1750, de 12 de novembro de 2018" in md
        and "TACHADO NA FONTE" in md
        and "Art. 1" in md
    )


def test_metadados_passam_na_auditoria_do_catalogo(tmp_path):
    pasta = ingerir(LEI, PLAN, lei_html(), tmp_path)
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    res = audit_snapshot(meta, pasta / "metadados.json", tmp_path, Hasher())
    assert res["problemas"] == []
    assert {c["arquivo"].rsplit("/", 1)[-1] for c in res["verificacoes"]} == {
        "original.html",
        "documento.md",
    }
    assert all(c["confere"] for c in res["verificacoes"])


def test_pdf_com_texto_vira_documento_e_passa_na_auditoria(tmp_path):
    cand = Candidato("https://x.gov.br/lei.pdf", "planalto", "unica")
    pasta = ingerir(
        LEI, cand, pdf_bytes("LEI N 10.833, DE 29 DE DEZEMBRO DE 2003. Art. 1 Texto."), tmp_path
    )
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    assert meta["original"] == "original.pdf" and meta["status"] == "coletado"
    assert "10.833" in (pasta / "documento.md").read_text(encoding="utf-8")
    assert audit_snapshot(meta, pasta / "metadados.json", tmp_path, Hasher())["problemas"] == []


def test_pdf_com_texto_de_outra_norma_nao_coleta(tmp_path):
    with pytest.raises(ValueError, match="identidade"):
        ingerir(
            LEI,
            Candidato("https://x.gov.br/l.pdf", "planalto", "unica"),
            pdf_bytes("LEI N 10.637, DE 30 DE DEZEMBRO DE 2002. Art. 1 Texto."),
            tmp_path,
        )


def test_pdf_sem_texto_nao_vira_documento_vazio(tmp_path):
    raw = pdf_bytes(None)
    pasta = ingerir(LEI, Candidato("https://x.gov.br/scan.pdf", "planalto", "unica"), raw, tmp_path)
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    assert (pasta / "original.pdf").read_bytes() == raw
    assert not (pasta / "documento.md").exists()
    assert meta["status"] == "extracao_pendente" and meta["original"] == "original.pdf"
    assert "markdown_sha256" not in meta or meta["markdown_sha256"] is None
    assert audit_snapshot(meta, pasta / "metadados.json", tmp_path, Hasher())["problemas"] == []
    assert (
        ingerir(LEI, Candidato("https://x.gov.br/scan.pdf", "planalto", "unica"), raw, tmp_path)
        == pasta
    )


# ---- caminho seguro, resolver_assunto ----


def test_chave_segura_estavel_curta_sem_colisao_e_valida_no_exfat():
    a = chave_segura(NormaId("portaria", 1, 2018, "federal", "rfb/pgfn").chave)
    b = chave_segura(NormaId("portaria", 1, 2018, "federal", "rfb-pgfn").chave)
    assert a != b and a == chave_segura(NormaId("portaria", 1, 2018, "federal", "rfb/pgfn").chave)
    for k in (
        a,
        b,
        chave_segura(LEI.chave),
        chave_segura(NormaId("lei", 1, None, "df").chave),
        chave_segura("x:y.:z. "),
    ):
        assert not set(k) & set('<>:"/\\|?*') and not k.endswith((".", " ")) and len(k) <= 60
    assert chave_segura(LEI.chave) != chave_segura(NormaId("lei", 10833, 2003, "df").chave)
    assert chave_segura(NormaId("lei", 1, None, "df").chave) != chave_segura(
        NormaId("lei", 1, 2000, "df").chave
    )


# ---- Fix round 1: fail-closed ----
from backend.crawler.fontes_normas import SemTextoAutomatico  # noqa: E402
from backend.crawler.normas_ingest import _html  # noqa: E402


@pytest.mark.parametrize(
    "texto,norma",
    [
        (
            "Regulamenta Lei nº 10.833, de 29 de dezembro de 2003.\nArt. 1º",
            NormaId("lei", 10833, 2003, "federal"),
        ),
        (
            "Altera Lei Complementar nº 123, de 14 de dezembro de 2006.\nArt. 1º",
            NormaId("lc", 123, 2006, "federal"),
        ),
        ("Revoga Lei nº 10.833/2003\nArt. 1º", NormaId("lei", 10833, 2003, "federal")),
        (
            "Produção de efeito Lei nº 10.637, de 30 de dezembro de 2002 LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003\nArt. 1º",
            NormaId("lei", 10637, 2002, "federal"),
        ),
        (
            "Lei nº 9.718, de 27 de novembro de 1998 (Texto compilado) Mensagem de veto LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003\nArt. 1º",
            NormaId("lei", 9718, 1998, "federal"),
        ),
        (
            "LEI Nº 10.833, DE 29.12.2003 Altera Lei nº 9.430, de 27 de dezembro de 1996\nArt. 1º",
            NormaId("lei", 9430, 1996, "federal"),
        ),
    ],
)
def test_citacao_nunca_vira_titulo(texto, norma):
    assert not validar_identidade(norma, texto)


@pytest.mark.parametrize(
    "texto",
    [
        "LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003\nArt. 1º",
        "LEI Nº 10.833, DE 29.12.2003\nArt. 1º",
        "LEI Nº 10.833, DE 29/12/2003\nArt. 1º",
        "LEI Nº 10.833, DE 29 DE DEZ. DE 2003\nArt. 1º",
        "LEI Nº 10.833/2003\nArt. 1º",
        "Lei nº 10.833, de 29 de dezembro de 2003\nArt. 1º",
        "Lei nº 10.833, de 29 de dez. de 2003 (Texto compilado)\nArt. 1º",
        "Produção de efeito Lei nº 10.637, de 30 de dezembro de 2002 LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003\nArt. 1º",
        "Lei nº 9.718, de 27 de novembro de 1998 (Texto compilado) Mensagem de veto LEI Nº 10.833, DE 29 DE DEZEMBRO DE 2003\nArt. 1º",
        "LEI Nº 10.833, DE 29.12.2003 Altera Lei nº 9.430, de 27 de dezembro de 1996\nArt. 1º",
    ],
)
def test_formatos_de_data_e_titulo_correto_passam(texto):
    assert validar_identidade(LEI, texto)


PORT33 = "PORTARIA Nº 33, DE 8 DE FEVEREIRO DE 2018"


def test_orgao_ausente_da_epigrafe_precisa_aparecer_no_cabecalho():
    pgfn = "PROCURADORIA-GERAL DA FAZENDA NACIONAL " + PORT33 + "\nArt. 1º"
    assert not validar_identidade(NormaId("portaria", 33, 2018, "federal", "rfb"), pgfn)
    assert validar_identidade(NormaId("portaria", 33, 2018, "federal", "pgfn"), pgfn)
    assert validar_identidade(NormaId("portaria", 33, 2018, "federal"), pgfn)
    assert not validar_identidade(
        NormaId("portaria", 33, 2018, "federal", "rfb"), PORT33 + "\nArt. 1º"
    )
    sigla = "MINISTÉRIO DA FAZENDA SECRETARIA DA RECEITA FEDERAL " + PORT33 + "\nArt. 1º"
    assert validar_identidade(NormaId("portaria", 33, 2018, "federal", "srf"), sigla)
    assert validar_identidade(
        NormaId("resol_cgsn", 5, 2007, "federal", "cgsn"),
        "COMITÊ GESTOR DO SIMPLES NACIONAL RESOLUÇÃO Nº 5, DE 30 DE MAIO DE 2007\nArt. 1º",
    )


def test_ato_conjunto_exige_o_mesmo_conjunto_de_orgaos():
    t = "PORTARIA CONJUNTA RFB/PGFN Nº 33, DE 8 DE FEVEREIRO DE 2018\nArt. 1º"
    p = lambda o: NormaId("portaria", 33, 2018, "federal", o)  # noqa: E731
    assert (
        validar_identidade(p("rfb/pgfn"), t)
        and validar_identidade(p("pgfn/rfb"), t)
        and validar_identidade(p(None), t)
    )
    assert not validar_identidade(p("rfb"), t) and not validar_identidade(p("pgfn"), t)


FIXTURES_16 = [
    ("planalto_lei_10833.raw", "planalto", NormaId("lei", 10833, 2003, "federal")),
    ("planalto_lei_10833_compilado.raw", "planalto", NormaId("lei", 10833, 2003, "federal")),
    ("planalto_decreto_70235.raw", "planalto", NormaId("decreto", 70235, 1972, "federal")),
    ("planalto_decreto_11356_2023.raw", "planalto", NormaId("decreto", 11356, 2023, "federal")),
    ("planalto_lei_14592_2023.raw", "planalto", NormaId("lei", 14592, 2023, "federal")),
    ("planalto_lei_15270_2025.raw", "planalto", NormaId("lei", 15270, 2025, "federal")),
    ("planalto_lc_214_2025.raw", "planalto", NormaId("lc", 214, 2025, "federal")),
    ("planalto_mpv_1185_2023.raw", "planalto", NormaId("mp", 1185, 2023, "federal")),
    ("planalto_mpv_881_2019.raw", "planalto", NormaId("mp", 881, 2019, "federal")),
    ("planalto_decreto_lei_4657_compilado.raw", "planalto", NormaId("dl", 4657, 1942, "federal")),
    ("planalto_lei_10865_2004.raw", "planalto", NormaId("lei", 10865, 2004, "federal")),
    ("planalto_lei_4320_1964.raw", "planalto", NormaId("lei", 4320, 1964, "federal")),
    ("planalto_decreto_3000_cabecalho.raw", "planalto", NormaId("decreto", 3000, 1999, "federal")),
    ("camara_lei_10833.raw", "camara", NormaId("lei", 10833, 2003, "federal")),
    ("camara_lei_10833_original.raw", "camara", NormaId("lei", 10833, 2003, "federal")),
    ("camara_decreto_70235.raw", "camara", NormaId("decreto", 70235, 1972, "federal")),
    ("sinj_lei_1254_atualizada.raw", "sinj", NormaId("lei", 1254, 1996, "df")),
    ("confaz_convenio_52_17.raw", "confaz", NormaId("convenio_icms", 52, 2017, "confaz")),
    ("confaz_convenio_100_97.raw", "confaz", NormaId("convenio_icms", 100, 1997, "confaz")),
]


@pytest.mark.parametrize("arquivo,fonte,norma", FIXTURES_16)
def test_paginas_reais_identificam_a_propria_norma_e_so_ela(arquivo, fonte, norma):
    import dataclasses

    pagina, _ = _html(Candidato("https://x.gov.br/a", fonte, "unica"), fx(arquivo))
    assert validar_identidade(norma, pagina)
    assert not validar_identidade(dataclasses.replace(norma, numero=norma.numero + 1), pagina)
    assert not validar_identidade(dataclasses.replace(norma, ano=norma.ano + 1), pagina)


def test_semtextoautomatico_e_resolver_assunto():
    e = SemTextoAutomatico("x")
    assert e.motivo == "x"

    class SemRede:
        def get(self, url):
            raise AssertionError("nao deve pedir nada")

    with pytest.raises(SemTextoAutomatico) as exc:
        resolver_assunto("IPTU", SemRede())
    assert "IPTU" in exc.value.motivo


# ---- SINJ: <p> sem </p> (Task 8a) ----


def test_sinj_p_abertos_nao_estoura_a_pilha_e_preserva_rasura(tmp_path):
    norma = NormaId("lei", 4567, 2011, "df")
    cand = Candidato(
        "https://www.sinj.df.gov.br/sinj/Norma/68572/Lei_4567.html", "sinj", "compilada"
    )
    pasta = ingerir(norma, cand, fx("sinj_lei_4567_p_abertos.raw"), tmp_path)
    md = (pasta / "documento.md").read_text(encoding="utf-8")
    assert md.count("Legisla") > 40  # o texto dos ~400 paragrafos abertos sobrevive
    assert "~~" in md and "Art. 9" in md  # a rasura (<s>) vira ~~ e o artigo tachado fica


def test_sinj_tabela_em_paragrafos_abertos_sobrevive(tmp_path):
    corpo = (
        "<h1>Lei 5 de 01/01/2020</h1>"
        + "".join(f"<p>Art. {i} Texto {i}" for i in range(1, 600))
        + "<table><tr><td>Faixa</td><td>12,5%</td></tr></table>"
    )
    raw = f'<html><body><div id="div_texto">{corpo}</div></body></html>'.encode()
    pasta = ingerir(
        NormaId("lei", 5, 2020, "df"),
        Candidato("https://x/s.html", "sinj", "compilada"),
        raw,
        tmp_path,
    )
    md = (pasta / "documento.md").read_text(encoding="utf-8")
    assert "Texto 599" in md and "12,5%" in md and "Faixa" in md


def test_erro_de_conversao_vira_erroconversao_nao_valueerror(tmp_path, monkeypatch):
    from backend.crawler import normas_ingest as ni

    monkeypatch.setattr(ni, "_convert", lambda *a: (_ for _ in ()).throw(RecursionError("fundo")))
    with pytest.raises(ni.ErroConversao, match="RecursionError"):
        ingerir(LEI, PLAN, lei_html(), tmp_path)


# ---- Task 8a: Constituicao, LODF e emenda constitucional ----

CF = NormaId("constituicao", 0, 1988, "federal")
LODF = NormaId("lodf", 0, 1993, "df")
SINJ_LODF = Candidato("https://www.sinj.df.gov.br/sinj/Norma/66634/LODF.html", "sinj", "compilada")


def test_constituicao_valida_pelo_titulo(tmp_path):
    cand = Candidato(
        "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", "planalto", "unica"
    )
    pasta = ingerir(CF, cand, fx("planalto_constituicao.raw"), tmp_path)
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    assert meta["tipo"] == "constituicao" and meta["numero"] == 0 and meta["ano"] == 1988
    assert "Constituição" in meta["titulo"] and "nº 0" not in meta["titulo"]
    with pytest.raises(ValueError, match="identidade"):  # outro texto sob o titulo da Constituicao
        ingerir(CF, cand, lei_html(), tmp_path)


def test_lei_organica_do_df_valida_pelo_titulo(tmp_path):
    pasta = ingerir(LODF, SINJ_LODF, fx("sinj_lodf.raw"), tmp_path)
    assert json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))["jurisdicao"] == "df"
    assert (pasta / "documento.md").is_file()
    with pytest.raises(ValueError, match="identidade"):
        ingerir(LODF, SINJ_LODF, fx("sinj_lei_4567_p_abertos.raw"), tmp_path)


def test_titulo_citado_no_meio_do_texto_nao_vale():
    assert not validar_identidade(
        CF,
        "LEI Nº 1, DE 1º DE JANEIRO DE 2000\nEmenta. Segundo a Constituição da República "
        "Federativa do Brasil de 1988, fica. Art. 1º Texto.",
    )
    assert validar_identidade(
        CF,
        "Presidência da República\nCONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL DE 1988\nArt. 1º X",
    )
    assert validar_identidade(CF, "CONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL\nArt. 1º X")
    assert validar_identidade(LODF, "LEI ORGÂNICA DO DISTRITO FEDERAL\nPREÂMBULO Art. 1º X")


@pytest.mark.parametrize(
    "norma, texto",
    [
        (
            CF,
            "EMENDA CONSTITUCIONAL Nº 132, DE 20 DE DEZEMBRO DE 2023\nCONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL DE 1988\nArt. 1º X",
        ),
        (CF, "CONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL DE 1967\nArt. 1º X"),
        (CF, "CONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL: comentada\nArt. 1º X"),
        (CF, "CONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL DE 1988 comentada\nArt. 1º X"),
        (
            LODF,
            "LEI Nº 5, DE 1º DE JANEIRO DE 2000\nLei Orgânica do Distrito Federal, altera.\nLei Orgânica do Distrito Federal\nArt. 1º X",
        ),
        (
            LODF,
            "EMENDA À LEI ORGÂNICA Nº 100, DE 2018\nLEI ORGÂNICA DO DISTRITO FEDERAL\nArt. 1º X",
        ),
        (LODF, "LEI ORGÂNICA DO DISTRITO FEDERAL DE 1990\nArt. 1º X"),
        (
            NormaId("constituicao", 0, 1967, "federal"),
            "CONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL DE 1988\nArt. 1º X",
        ),
    ],
)
def test_titulo_de_numero_zero_exige_linha_inteira_e_primeira_epigrafe(norma, texto):
    assert not validar_identidade(norma, texto)


def test_emenda_constitucional_valida_numero_e_rejeita_a_errada(tmp_path):
    ec132 = NormaId("ec", 132, 2023, "federal")
    cand = Candidato(
        "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc132.htm",
        "planalto",
        "unica",
    )
    assert ingerir(ec132, cand, fx("planalto_emc_132.raw"), tmp_path).is_dir()
    with pytest.raises(ValueError, match="identidade"):  # a pagina da EC 103 sob a EC 132
        ingerir(ec132, cand, fx("planalto_emc_103.raw"), tmp_path)


# ---- Fix round 1 ----


def _sinj_md(corpo, tmp_path, titulo="Lei 5 de 01/01/2020"):
    raw = f'<html><body><div id="div_texto"><h1>{titulo}</h1>{corpo}</div></body></html>'.encode()
    pasta = ingerir(
        NormaId("lei", 5, 2020, "df"),
        Candidato("https://x/s.html", "sinj", "compilada"),
        raw,
        tmp_path,
    )
    return (pasta / "documento.md").read_text(encoding="utf-8")


def test_sinj_rasura_que_atravessa_paragrafos_abertos_nao_perde_o_segundo_trecho(tmp_path):
    md = _sinj_md("<p><s>riscado um<p>riscado dois</s><p>normal", tmp_path)
    import re

    assert re.search(r"~~[^~]*riscado um[^~]*~~", md) and re.search(
        r"~~[^~]*riscado dois[^~]*~~", md
    )
    assert not re.search(r"~~[^~]*normal[^~]*~~", md) and md.index("riscado dois") < md.index(
        "normal"
    )


def test_sinj_tabela_dentro_de_paragrafo_aberto_nao_e_partida(tmp_path):
    md = _sinj_md(
        "<p>intro<table><tr><td><p>AA</td><td><p>BB</td></tr><tr><td><p>CC</td><td><p>DD</td></tr></table>"
        "<p>depois",
        tmp_path,
    )
    linhas = [ln for ln in md.splitlines() if "|" in ln]
    assert any("AA" in ln and "BB" in ln for ln in linhas) and any(
        "CC" in ln and "DD" in ln for ln in linhas
    )
    assert md.index("intro") < md.index("AA") < md.index("depois")
    solto = _sinj_md(
        "<p>intro<table><tr><td><p>AA<td><p>BB<tr><td><p>CC<td><p>DD</table><p>depois",
        tmp_path / "b",
    )
    assert all(t in solto for t in ("AA", "BB", "CC", "DD")) and solto.index("intro") < solto.index(
        "AA"
    ) < solto.index("depois")


def test_valueerror_da_conversao_vira_erroconversao_mas_identidade_continua_valueerror(
    tmp_path, monkeypatch
):
    from backend.crawler import normas_ingest as ni

    monkeypatch.setattr(
        ni, "_convert", lambda *a: b"\xff".decode("utf-8")
    )  # UnicodeDecodeError e subclasse de ValueError
    with pytest.raises(ni.ErroConversao, match="UnicodeDecodeError"):
        ingerir(LEI, PLAN, lei_html(), tmp_path)
    monkeypatch.undo()
    with pytest.raises(ValueError, match="identidade") as e:
        ingerir(NormaId("lei", 1, 2003, "federal"), PLAN, lei_html(), tmp_path)
    assert not isinstance(e.value, ni.ErroConversao)
    with pytest.raises(
        ni.ErroConversao
    ):  # JSON da Receita malformado: falha de leitura, nao identidade
        ingerir(
            NormaId("portaria", 1, 2018, "federal", "rfb"),
            Candidato("https://x/ato/1/visao/original", "receita", "original"),
            b"{nao e json",
            tmp_path,
        )


def test_texto_depois_de_body_fechado_antes_da_hora_nao_se_perde(tmp_path):
    """Planalto: o Codigo Civil fecha </body></html> a 4% da pagina; o resto da lei vem depois."""
    norma = NormaId("lei", 10406, 2002, "federal")
    raw = (
        "<html><head><title>L10406</title></head><body><p>LEI Nº 10.406, DE 10 DE JANEIRO DE 2002</p>"
        "<p>Art. 1º Toda pessoa.</p></body></html><p><strike>Art. 2º revogado.</strike></p>"
        "<p>Art. 2.046. Ultimo artigo.</p>"
    ).encode("utf-8")
    cand = Candidato(
        "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406.htm", "planalto", "unica"
    )
    md = (ingerir(norma, cand, raw, tmp_path) / "documento.md").read_text(encoding="utf-8")
    assert "Art. 2.046" in md and "~~Art. 2º revogado.~~" in md
    assert "L10406" not in md
