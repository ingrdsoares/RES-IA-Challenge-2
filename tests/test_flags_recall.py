"""--contexto-norma e --corte-por-artigo; sem as flags a carga continua a da knowledge_base_v2."""

import pytest

from src.rag import csv_para_qdrant as m

LINHA = {
    "documento_id": "d1",
    "versao_id": "v1",
    "titulo": "IN 1503/2014",
    "natureza": "legislacao",
    "frente": "tributacao-lucro",
    "source_url": "https://fonte.test/d1",
    "coletado_em": "2026-11-04T10:00:00+00:00",
    "vigencia_fonte": "",
    "texto": "Art. 1º Regra curta.\nArt. 2º Outra.",
}
# Artigo de ~2500 caracteres, com parágrafos, seguido de um artigo curto.
GRANDE = (
    "Art. 5º Caput do artigo.\n"
    + "\n".join(f"§ {i}º Texto do parágrafo número {i}. " + "palavra " * 60 for i in range(1, 7))
    + "\nArt. 6º Curto."
)


@pytest.fixture(autouse=True)
def restaura():
    yield
    m.configurar(2000, False)


def itens(linha=LINHA):
    return list(m.itens_do_documento(linha, m.estatisticas_novas()))


def test_padrao_nao_muda():
    m.configurar(2000, False)
    saida = itens()
    assert [t for _, t, _ in saida] == [
        "[DOCUMENTO: in_1503_2014 | FONTE: IN 1503/2014 | CAPÍTULO: Geral | ARTIGO: Art. 1º | "
        "TEMA: Art. 1º]\nArt. 1º Regra curta.",
        "[DOCUMENTO: in_1503_2014 | FONTE: IN 1503/2014 | CAPÍTULO: Geral | ARTIGO: Art. 2º | "
        "TEMA: Art. 2º]\nArt. 2º Outra.",
    ]
    assert [d["chunk_id"] for _, _, d in saida] == ["in_1503_2014_art_1º", "in_1503_2014_art_2º"]
    assert all("carga" not in d for _, _, d in saida)


def test_contexto_norma_entra_no_mesmo_colchete_e_no_esparso():
    m.configurar(2000, False, contexto_norma=True)
    _, texto, dados = itens()[0]
    primeira = texto.split("\n")[0]
    assert primeira.startswith(
        "[Instrução Normativa 1503 | art. 1 | legislacao | tributacao lucro | DOCUMENTO: "
    )
    assert primeira.endswith("]") and primeira.count("]") == 1
    assert texto.endswith("\nArt. 1º Regra curta.")
    assert dados["carga"] == "contexto"
    assert m.vetor_documento(texto) != m.vetor_documento(itens_padrao()[0][1])


def itens_padrao():
    m.configurar(2000, False)
    return itens()


def test_contexto_nao_repete_o_tipo_quando_o_titulo_ja_tem():
    m.configurar(2000, False, contexto_norma=True)
    linha = LINHA | {
        "titulo": "Lei nº 9.249, de 26 de dezembro de 1995",
        "natureza": "nao_informada",
    }
    texto = itens(linha)[0][1]
    assert texto.startswith("[art. 1 | tributacao lucro | DOCUMENTO: ")


def test_corte_por_artigo_um_ponto_por_artigo_com_rotulo_em_cada_parte():
    linha = LINHA | {"texto": GRANDE}
    m.configurar(1000, False)
    padrao = itens(linha)
    m.configurar(1000, False, corte_por_artigo=True)
    novo = itens(linha)
    art5 = [d for _, _, d in novo if d["artigo"] == "5"]
    assert len(art5) >= 3
    assert all(d["chunk_id"].startswith("in_1503_2014_art_5º_w") for d in art5)
    assert all("ARTIGO: Art. 5º" in t for _, t, d in novo if d["artigo"] == "5")
    assert all(len(t) <= 1000 + 50 for _, t, _ in novo)
    # parágrafo solto repetindo o caput era o padrão; aqui não há mais "Contexto do Artigo"
    assert any("Contexto do Artigo" in t for _, t, _ in padrao)
    assert not any("Contexto do Artigo" in t for _, t, _ in novo)
    # artigo curto vira um ponto só, igual ao padrão
    assert [t for _, t, d in novo if d["artigo"] == "6"] == [
        t for _, t, d in padrao if d["artigo"] == "6"
    ]


def test_corte_por_artigo_nao_mexe_em_outra_natureza():
    linha = LINHA | {"texto": GRANDE, "natureza": "consulta_tributaria"}
    m.configurar(1000, False)
    antes = itens(linha)
    m.configurar(1000, False, corte_por_artigo=True)
    assert [t for _, t, _ in itens(linha)] == [t for _, t, _ in antes]


def test_flags_combinadas():
    m.configurar(1000, False, contexto_norma=True, corte_por_artigo=True)
    saida = itens(LINHA | {"texto": GRANDE})
    assert all(d["carga"] == "contexto+artigo" for _, _, d in saida)
    assert all(t.startswith("[Instrução Normativa 1503 | art. ") for _, t, _ in saida)


def test_retomar_nao_mistura_configuracoes(tmp_path):
    import csv

    from app.config import Settings
    from app.vector_store import VectorStore
    from qdrant_client import QdrantClient

    caminho = tmp_path / "r.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(LINHA))
        w.writeheader()
        w.writerow(LINHA)
    settings = Settings()
    client = QdrantClient(":memory:")
    VectorStore(settings.model_copy(update={"collection_name": "c"}), client).ensure_collection()

    def embed(textos):
        return [[0.1] * settings.embedding_dimensions for _ in textos]

    def carga(**kw):
        return m.ingerir(
            caminho, settings=settings, client=client, embed=embed, colecao="c", retomar=True
        )

    m.configurar(2000, False)
    assert carga()["gravados"] == 2
    assert carga()["pulados"] == 1
    m.configurar(2000, False, contexto_norma=True)
    r = carga()
    assert (r["pulados"], r["gravados"]) == (0, 2)
    assert carga()["pulados"] == 1
