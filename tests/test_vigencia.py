"""Data do ato (src/rag/vigencia) e a flag --vigencia-do-titulo; sem a flag nada muda."""

import pytest

from src.rag import csv_para_qdrant as m
from src.rag.vigencia import data_do_ato, data_do_titulo, data_iso_br


@pytest.mark.parametrize(
    "titulo, esperado",
    [
        ("LEI Nº 3.531, DE 03 DE JANEIRO 2005", "2005-01-03"),  # sem "de" antes do ano
        ("Lei nº 9.249, de 26 de dezembro de 1995", "1995-12-26"),
        ("Decreto nº 1, de 1º de março de 2020", "2020-03-01"),  # ordinal e cedilha
        ("Portaria 2, de 1o de fevereiro de 2021", "2021-02-01"),
        ("Solução de Consulta Cosit nº 98105, de 23 de abril de 2025", "2025-04-23"),
        ("Lei nº 5, de 31 de fevereiro de 2020", None),  # dia inexistente
        ("Lei nº 5, de 3 de janeiero de 2020", None),  # mês inválido
        ("Altera a Lei 5 de 3 de janeiro de 2020", None),  # sem vírgula: pode ser norma citada
        ("SC 178/2026", None),
        ("", None),
        (None, None),
    ],
)
def test_data_do_titulo(titulo, esperado):
    assert data_do_titulo(titulo) == esperado


def test_data_iso_br():
    assert data_iso_br("25/06/2025") == "2025-06-25"
    assert data_iso_br("2019-04-08") == "2019-04-08"
    assert data_iso_br("2019-04-08T10:00:00+00:00") == "2019-04-08"
    assert data_iso_br("31/02/2025") is None
    assert data_iso_br("lixo") is None
    assert data_iso_br(None) is None


def test_data_do_ato_prefere_publicacao_e_ignora_consolidado():
    meta = {"data": "2012-11-29", "data_publicacao_fonte": "04/12/2012"}
    assert data_do_ato("X", "texto", meta) == "2012-12-04"
    assert data_do_ato("X", "texto", {"data": "29/11/2012"}) == "2012-11-29"
    assert (
        data_do_ato("X", "## Visão solicitada multivigente; retornada multivigente", meta) is None
    )
    anotado = "alínea [(Alínea alterado(a) pelo(a) Lei 5548 de 15/10/2015)](x)"
    assert data_do_ato("LEI Nº 1.254, DE 8 DE NOVEMBRO DE 1996", anotado) is None


def test_data_do_ato_dodf():
    texto = "# SC\n\n**PUBLICADA NO DODF Nº 74, DE\n20/04/2022, PG 5 E 6.**\n"
    assert data_do_ato("Declaração de Ineficácia 13/2022", texto) == "2022-04-20"
    assert data_do_ato("Declaração de Ineficácia 13/2022", "sem cabeçalho") is None


LINHA = {
    "documento_id": "d1",
    "versao_id": "v1",
    "titulo": "LEI COMPLEMENTAR Nº 1.025, DE 25 DE OUTUBRO DE 2023",
    "natureza": "legislacao",
    "frente": "",
    "source_url": "https://fonte.test/d1",
    "coletado_em": "2026-11-04T10:00:00+00:00",
    "vigencia_fonte": "",
    "texto": "Art. 1º Regra curta.",
}


def _payload(linha):
    return next(m.itens_do_documento(linha, m.estatisticas_novas()))[2]


@pytest.fixture(autouse=True)
def restaura():
    yield
    m.configurar(2000, False)


def test_flag_desligada_nao_muda_payload():
    m.configurar(2000, False)
    assert "effective_date" not in _payload(LINHA)
    assert _payload(LINHA | {"vigencia_fonte": "2024-01-22"})["effective_date"] == "2024-01-22"


def test_flag_deriva_so_quando_coluna_vazia():
    m.configurar(2000, False, vigencia_do_titulo=True)
    assert _payload(LINHA)["effective_date"] == "2023-10-25"
    assert _payload(LINHA | {"vigencia_fonte": "2024-01-22"})["effective_date"] == "2024-01-22"
    assert _payload(LINHA | {"vigencia_fonte": "lixo"})["effective_date"] == "2023-10-25"
    assert "effective_date" not in _payload(LINHA | {"titulo": "SC 178/2026"})
    consolidado = LINHA | {"texto": "Art. 1º X (Redação dada pela Lei 5 de 2024)"}
    assert "effective_date" not in _payload(consolidado)
