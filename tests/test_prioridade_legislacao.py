"""Natureza das leis na carga e vaga reservada para legislação no top-k (caso q08)."""

import pytest
from app.models import SYSTEM_PROMPT
from app.rag import combinar, legislacao_reservada
from app.schemas import Source

from src.rag.csv_para_qdrant import natureza_do_documento


def fonte(i: int, natureza: str | None, doc: str | None = None) -> Source:
    return Source(
        id=i,
        text=f"trecho {i}",
        source="https://exemplo.gov.br",
        score=1.0,
        document_id=doc or f"doc{i}",
        natureza=natureza,
    )


@pytest.mark.parametrize(
    "titulo",
    [
        "Lei nº 9.249, de 26 de dezembro de 1995",
        "Lei Complementar nº 123, de 14 de dezembro de 2006",
        "Lei nº 5.172, de 25 de outubro de 1966 — Código Tributário Nacional",
        "Decreto nº 9.580, de 22 de novembro de 2018 — RIR",
        "Ajuste SINIEF 7, de 30 de setembro de 2005 — NF-e",
    ],
)
def test_lei_sem_natureza_vira_legislacao(titulo):
    assert natureza_do_documento(titulo, "nao_informada") == "legislacao"
    assert natureza_do_documento(titulo, None) == "legislacao"


def test_natureza_informada_e_titulos_que_nao_sao_lei_ficam_iguais():
    assert natureza_do_documento("Lei nº 9.249", "consulta_tributaria") == "consulta_tributaria"
    assert natureza_do_documento("SC 4015/2025", "nao_informada") == "nao_informada"
    assert natureza_do_documento("Manual do MEI sobre a Lei 123", "nao_informada") == (
        "nao_informada"
    )
    assert natureza_do_documento(None, "") is None


def test_legislacao_reservada_pega_as_primeiras_leis_na_ordem():
    ordem = [
        fonte(1, "interpretacao_administrativa"),
        fonte(2, "legislacao"),
        fonte(3, "consulta_tributaria"),
        fonte(4, "legislacao"),
    ]
    assert [f.id for f in legislacao_reservada(ordem, 1)] == [2]
    assert [f.id for f in legislacao_reservada(ordem, 2)] == [2, 4]
    assert legislacao_reservada(ordem, 0) == []
    assert legislacao_reservada([fonte(1, "consulta_tributaria")], 1) == []


def test_lei_mal_ranqueada_entra_no_top_k():
    # Seis soluções de consulta na frente, como na q08; a lei estava em 7º e ficava de fora.
    consultas = [fonte(i, "interpretacao_administrativa") for i in range(1, 7)]
    lei = fonte(7, "legislacao")
    ordem = consultas + [lei]
    sem = combinar([], ordem[:2] + ordem, 6)
    com = combinar([], ordem[:2] + legislacao_reservada(ordem, 1) + ordem, 6)
    assert lei not in sem
    assert [f.id for f in com] == [1, 2, 7, 3, 4, 5]


def test_prompt_pede_condicao_do_percentual_e_regra_geral():
    assert "percentual, alíquota ou prazo" in SYSTEM_PROMPT
    assert "regra geral da lei" in SYSTEM_PROMPT


def test_artigo_citado_por_varias_consultas_e_seguido():
    from app.rag import artigos_mais_citados

    def sc(i, texto):
        return Source(id=i, text=texto, source="https://x.gov.br", score=1.0)

    fontes = [
        sc(1, "Aplica-se o art. 15 da Lei nº 9.249, de 1995, aos serviços hospitalares."),
        sc(2, "Conforme o art. 15 da Lei nº 9.249, de 1995, e o art. 20 da mesma lei."),
        sc(3, "Nos termos do art. 3º da Lei nº 9.718, de 1998."),
    ]
    assert artigos_mais_citados(fontes) == [("lei:9249", "15")]
    # Citado por uma fonte só não basta; o mesmo texto repetido na fonte conta uma vez.
    assert artigos_mais_citados(fontes[2:]) == []
    assert artigos_mais_citados([sc(1, "art. 15 da Lei nº 9.249 e art. 15 da Lei nº 9.249")]) == []


def test_modelo_ve_o_tipo_do_documento():
    import json

    from app.models import _messages

    docs = json.loads(
        _messages("pergunta", [fonte(1, "legislacao"), fonte(2, "interpretacao_administrativa")])[
            1
        ]["content"].split("\n")[1]
    )
    assert docs[0]["tipo"] == "lei ou norma"
    assert docs[1]["tipo"] == "solução de consulta (caso concreto)"
