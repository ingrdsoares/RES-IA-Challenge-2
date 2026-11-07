import json
from types import SimpleNamespace

import pytest

from backend.crawler.inventario_normas import inventariar


@pytest.fixture
def run(tmp_path):
    """Monta execucao minima: add(doc_id, titulo, natureza, texto, frente, conteudo_id)."""
    d = tmp_path / "run"
    (d / "conteudos").mkdir(parents=True)
    linhas = []

    def add(doc, titulo, natureza="legislacao", texto="", frente="legislacao", conteudo=None):
        conteudo = conteudo or f"c-{doc}"
        if texto or not (d / "conteudos" / f"{conteudo}.md").exists():
            (d / "conteudos" / f"{conteudo}.md").write_text(texto, encoding="utf-8")
        linhas.append(
            {
                "documento_id": doc,
                "titulo": titulo,
                "natureza": natureza,
                "frente": frente,
                "conteudo_id": conteudo,
            }
        )
        (d / "ocorrencias.jsonl").write_text(
            "\n".join(json.dumps(x) for x in linhas), encoding="utf-8"
        )

    sementes = tmp_path / "sementes.json"
    sementes.write_text("[]", encoding="utf-8")
    return SimpleNamespace(add=add, dir=d, sementes=sementes, destino=tmp_path / "out")


def rodar(run):
    r = inventariar(run.dir, run.sementes, run.destino, processos=1)
    assert json.loads((run.destino / "inventario.json").read_text(encoding="utf-8")) == r
    return {x["chave"]: x for x in r["linhas"]}


def test_norma_coletada_com_titulo_abreviado_nao_falta(run):
    run.add("d1", "Decreto DF nº 25.508/2005")
    run.add(
        "d2",
        "Outro",
        texto="conforme o Decreto Distrital nº 25.508, de 2005",
        frente="distrital-df",
    )
    assert rodar(run)["df:decreto:-:25508:2005"]["situacao"] == "ja_existia"


def test_interpretacao_nao_conta_como_norma_coletada(run):
    run.add("d1", "Lei 9.430/1996", natureza="interpretacao_administrativa")
    run.add("d2", "SC", natureza="consulta_tributaria", texto="Lei nº 9.430/1996")
    assert rodar(run)["federal:lei:-:9430:1996"]["situacao"] == "pendente"


def test_citacao_sem_ano_com_varios_candidatos_fica_ambigua(run):
    run.add("d1", "x", texto="Lei nº 500, de 1990")
    run.add("d2", "y", texto="Lei nº 500, de 2001")
    run.add("d3", "z", texto="Lei nº 500")
    r = rodar(run)
    assert r["federal:lei:-:500:?"]["situacao"] == "ambigua" and r["federal:lei:-:500:?"]["motivo"]
    assert r["federal:lei:-:500:1990"]["situacao"] == "pendente"


def test_citacao_sem_ano_com_um_candidato_liga(run):
    run.add("d1", "x", texto="Lei nº 500, de 1990")
    run.add("d3", "z", texto="Lei nº 500")
    r = rodar(run)
    assert "federal:lei:-:500:?" not in r
    assert (
        r["federal:lei:-:500:1990"]["situacao"] == "pendente"
        and r["federal:lei:-:500:1990"]["citado_em"] == 2
    )


def test_sementes_sempre_entram(run):
    run.sementes.write_text(
        json.dumps(
            [
                {"tipo": "decreto", "numero": 7212, "ano": 2010, "jurisdicao": "federal"},
                {
                    "tipo": "constituicao",
                    "numero": 0,
                    "ano": 1988,
                    "jurisdicao": "federal",
                    "titulo_regex": "constituicao federal",
                },
                {
                    "tipo": "assunto",
                    "numero": 0,
                    "ano": None,
                    "jurisdicao": "df",
                    "assunto": "IPTU",
                },
            ]
        ),
        encoding="utf-8",
    )
    run.add("d1", "Constituição Federal de 1988")
    r = rodar(run)
    assert r["federal:decreto:-:7212:2010"]["origem"] == "semente"
    assert r["federal:decreto:-:7212:2010"]["situacao"] == "pendente"
    assert r["federal:constituicao:-:0:1988"]["situacao"] == "ja_existia"
    iptu = [x for x in r.values() if x.get("assunto") == "IPTU"][0]
    assert iptu["situacao"] == "pendente" and iptu["origem"] == "semente"


def test_citacoes_contam_documentos_nao_textos(run):
    run.add("d1", "a", texto="Lei nº 9.430/1996", conteudo="comum")
    run.add("d2", "b", conteudo="comum")
    run.add("d3", "c", texto="Lei nº 9.430/1996 e Lei nº 9.430/1996")
    assert rodar(run)["federal:lei:-:9430:1996"]["citado_em"] == 3


def test_toda_linha_tem_situacao(run):
    run.add(
        "d1",
        "a",
        texto="Lei nº 9.430/1996, Portaria RFB nº 12/2020 e Lei nº 4.567/2011",
        frente="consultas-df-amplas",
    )
    r = rodar(run)
    assert r and all(x["situacao"] in ("ja_existia", "ambigua", "pendente") for x in r.values())


def test_titulo_sem_ano_e_sem_orgao_atua_como_curinga(run):
    run.add("d1", "lc214")
    run.add("d2", "Port. 27/2022")
    run.add("d3", "x", texto="Lei Complementar nº 214/2025 e Portaria RFB nº 27/2022")
    r = rodar(run)
    assert r["federal:lc:-:214:2025"]["situacao"] == "ja_existia"
    assert r["federal:portaria:rfb:27:2022"]["situacao"] == "ja_existia"


def test_citacao_do_df_com_duas_candidatas(run):
    run.add("d1", "Lei 4.567/2011")  # coletada, federal
    run.add("d2", "x", texto="Lei nº 4.567/2011 e Lei nº 7.000/2015", frente="distrital-df")
    r = rodar(run)
    assert r["federal:lei:-:4567:2011"]["situacao"] == "ja_existia"
    a, b = r["df:lei:-:7000:2015"], r["federal:lei:-:7000:2015"]
    assert (
        a["situacao"] == b["situacao"] == "pendente" and a["ligacao"] == b["ligacao"] == "ambigua"
    )


def _docs(run, texto, n, prefixo, **kw):
    for i in range(n):
        run.add(f"{prefixo}{i}", "x", texto=texto, **kw)


def test_ano_dominante_em_numeracao_continua(run):
    _docs(run, "Lei nº 10.833, de 2003", 453, "a")
    _docs(run, "Lei nº 10.833", 51, "b")
    _docs(run, "Lei nº 10.833, de 2002", 10, "c")
    r = rodar(run)
    assert (
        r["federal:lei:-:10833:2003"]["citado_em"] == 504
        and r["federal:lei:-:10833:2003"]["situacao"] == "pendente"
    )
    assert "federal:lei:-:10833:?" not in r
    assert r["federal:lei:-:10833:2002"]["situacao"] == "ambigua"
    assert (
        "dominante 2003" in r["federal:lei:-:10833:2002"]["motivo"]
        and r["federal:lei:-:10833:2002"]["citado_em"] == 10
    )


def test_portaria_nao_usa_ano_dominante(run):
    _docs(run, "Portaria RFB nº 100, de 2020", 100, "a")
    _docs(run, "Portaria RFB nº 100, de 2021", 5, "b")
    r = rodar(run)
    assert (
        r["federal:portaria:rfb:100:2020"]["situacao"]
        == r["federal:portaria:rfb:100:2021"]["situacao"]
        == "pendente"
    )


def test_gemea_dobra_na_linha_certa(run):
    run.add("d1", "x", texto="Decreto Distrital nº 33.269, de 2011", frente="distrital-df")
    run.add("d2", "x", texto="Decreto nº 33.269, de 2011", frente="distrital-df")
    run.add(
        "d3",
        "x",
        texto="Decreto nº 33.269, de 2011 e Decreto nº 40.000, de 2015",
        frente="distrital-df",
    )
    r = rodar(run)
    assert (
        "federal:decreto:-:33269:2011" not in r and r["df:decreto:-:33269:2011"]["citado_em"] == 3
    )
    assert (
        r["df:decreto:-:40000:2015"]["candidata_ordem"] == 0
        and r["federal:decreto:-:40000:2015"]["candidata_ordem"] == 1
    )


def test_citada_sem_ano_nao_casa_coletada_com_ano_fora_do_conjunto(run):
    run.add("d1", "Portaria 27/2022")
    run.add("d2", "Lei 9.430/1996")
    run.add("d3", "x", texto="Portaria RFB nº 27 e Lei nº 9.430")
    r = rodar(run)
    assert r["federal:portaria:rfb:27:?"]["situacao"] == "pendente"
    assert r["federal:lei:-:9430:1996"]["situacao"] == "ja_existia"
