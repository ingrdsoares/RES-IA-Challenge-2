import pytest
from app.config import Settings
from app.models import citacoes_validas
from app.normas import chaves_normas, nome_norma
from app.rag import RagService, combinar
from app.schemas import Source
from app.sparse import tokens, vetor_consulta, vetor_documento
from app.vector_store import DENSE, SPARSE, VectorStore
from qdrant_client import QdrantClient, models


def ponto(pid, vetor, texto, **payload):
    i, v = vetor_documento(texto)
    return models.PointStruct(
        id=pid,
        vector={DENSE: vetor, SPARSE: models.SparseVector(indices=i, values=v)},
        payload={"text": texto, "source": "Fonte", **payload},
    )


def eixo(i):
    vetor = [0.0] * 1024
    vetor[i] = 1.0
    return vetor


def fonte(pid, texto):
    return Source(id=pid, text=texto, source="Fonte", score=0.9)


@pytest.fixture
def client():
    client = QdrantClient(":memory:")
    yield client
    client.close()


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Decreto Nº 43.982/2022", ["decreto", "43982", "2022"]),
        ("art. 8º da LC 87/96", ["art", "8", "lc", "87", "96"]),
    ],
)
def test_tokens_preservam_numero_de_norma(texto, esperado):
    assert tokens(texto) == esperado


def test_vetores_esparsos_alinhados_e_consulta_sem_repeticao():
    indices, valores = vetor_documento("ICMS ICMS base")
    assert len(indices) == len(valores) == 2 and indices == sorted(indices)
    assert vetor_consulta("ICMS ICMS")[1] == [1.0]
    assert vetor_consulta("de a o") == ([], [])


@pytest.mark.parametrize(
    "texto",
    [
        "segundo a Lei Complementar 87?",
        "Lei Complementar nº 87, de 13 de setembro de 1996",
        "LC 87/96",
        "lc87",
        "a Lei Kandir",
    ],
)
def test_formas_da_lc_87_dao_a_mesma_chave(texto):
    assert chaves_normas(texto) == ["lc:87"]


@pytest.mark.parametrize(
    ("texto", "chave"),
    [
        ("Decreto nº 43.982/2022", "decreto:43982"),
        ("Decreto DF nº 25.508/2005 — Regulamento do ISS", "decreto:25508"),
        ("LEI Nº 5.005, DE 21 DE DEZEMBRO DE 2012", "lei:5005"),
        ("Emenda Constitucional nº 132/2023", "ec:132"),
        ("ec132", "ec:132"),
        ("IN 1700/2017", "in:1700"),
        ("Instrução Normativa RFB nº 2.110", "in:2110"),
        ("Resol. 140/2018", "resolucao:140"),
        ("Resolução CGSN nº 140", "resolucao:140"),
        ("Port. 374/2002", "portaria:374"),
        ("Decreto-Lei nº 1.598", "dl:1598"),
        ("Código Tributário Nacional", "lei:5172"),
    ],
)
def test_chaves_de_normas(texto, chave):
    assert chaves_normas(texto) == [chave]


def test_sem_norma_nao_gera_chave():
    assert chaves_normas("Qual a base de cálculo do ICMS em 2024?") == []
    assert chaves_normas(None) == []
    assert nome_norma("lc:87") == "Lei Complementar 87"


def test_termo_raro_entra_pela_busca_esparsa(client):
    store = VectorStore(Settings(), client)
    store.ensure_collection()
    client.upsert(
        "knowledge_base",
        [
            ponto(1, eixo(0), "texto generico de exemplo"),
            ponto(2, [0.6, 0.8] + [0.0] * 1022, "regra do codigo 6201 aqui"),
        ],
    )
    ids = [s.id for s in store.search(eixo(0), "codigo 6201")]
    assert ids[0] == 2 and set(ids) == {1, 2}
    assert next(
        s for s in store.search(eixo(0), "codigo 6201") if s.id == 2
    ).score == pytest.approx(0.6)


def test_trecho_so_esparso_abaixo_do_limiar_nao_entra(client):
    store = VectorStore(Settings(), client)
    store.ensure_collection()
    client.upsert("knowledge_base", [ponto(1, eixo(1), "offshore em paraiso fiscal")])
    assert store.search(eixo(0), "offshore") == []


def test_falha_na_busca_esparsa_cai_para_a_densa(client, monkeypatch):
    store = VectorStore(Settings(), client)
    store.ensure_collection()
    client.upsert("knowledge_base", [ponto(1, eixo(0), "texto")])
    original = client.query_points

    def falha_esparsa(*args, **kwargs):
        if kwargs.get("using") == SPARSE:
            raise RuntimeError("sem índice")
        return original(*args, **kwargs)

    monkeypatch.setattr(client, "query_points", falha_esparsa)
    assert [s.id for s in store.search(eixo(0), "texto")] == [1]


def test_norma_citada_achada_e_ausente(client):
    store = VectorStore(Settings(), client)
    store.ensure_collection()
    client.upsert(
        "knowledge_base",
        [
            ponto(1, eixo(0), "outro", norma=[]),
            ponto(2, [0.6, 0.8] + [0.0] * 1022, "lei a", norma=["lc:87"]),
            ponto(3, [0.6, 0.8] + [0.0] * 1022, "lei b", norma=["lc:87"]),
            ponto(4, [0.6, 0.8] + [0.0] * 1022, "lei c", norma=["lc:87"]),
        ],
    )
    achados, ausentes = store.search_norms(eixo(0), ["lc:87", "decreto:43982"])
    assert {s.id for s in achados} <= {2, 3, 4} and len(achados) == 2
    assert ausentes == ["decreto:43982"]


def test_combinar_poe_norma_na_frente_tira_corpo_repetido_e_corta():
    cabecalho = "[DOCUMENTO: x]\n"
    citados = [fonte(9, cabecalho + "lei")]
    hits = [
        fonte(1, cabecalho + "corpo  igual"),
        fonte(2, "[DOCUMENTO: y]\ncorpo igual"),
        fonte(9, cabecalho + "lei"),
        fonte(3, cabecalho + "outro"),
        fonte(4, cabecalho + "sobra"),
    ]
    assert [s.id for s in combinar(citados, hits, 3)] == [9, 1, 3]


def test_citacoes_fora_das_fontes_saem_e_ficam_avisadas():
    texto, removidas = citacoes_validas("Regra [1], [2] e [211].", 2)
    assert "[211]" not in texto and "[1]" in texto and "[2]" in texto and removidas
    assert citacoes_validas("Regra [1].", 2) == ("Regra [1].", False)


class ModeloFalso:
    def __init__(self):
        self.ausentes = None

    def embed_question(self, pergunta):
        return eixo(0)

    def answer(self, pergunta, fontes, ausentes=()):
        self.ausentes = list(ausentes)
        return "Resposta [1] e [7]"


def test_consulta_reserva_norma_avisa_ausente_e_valida_citacao(client):
    settings = Settings(top_k=2)
    store = VectorStore(settings, client)
    store.ensure_collection()
    client.upsert(
        "knowledge_base",
        [
            ponto(1, eixo(0), "muito parecido", norma=[]),
            ponto(2, eixo(0), "tambem parecido", norma=[]),
            ponto(3, [0.6, 0.8] + [0.0] * 1022, "texto da lei", norma=["lc:87"]),
        ],
    )
    modelo = ModeloFalso()
    resposta = RagService(settings, store, modelo).query("LC 87 e Decreto 43.982?")
    assert resposta.sources[0].id == 3
    assert modelo.ausentes == ["decreto:43982"]
    assert "[7]" not in resposta.answer
