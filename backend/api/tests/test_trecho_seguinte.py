from app.config import Settings
from app.rag import RagService, expandir_janela, juntar_continuacoes
from app.schemas import Source
from app.sparse import vetor_documento
from app.vector_store import DENSE, SPARSE, VectorStore
from qdrant_client import QdrantClient, models

CORTADO = "[DOCUMENTO: x]\nO fato gerador é aquele previsto nos seguintes termos:"
SEGUINTE = "[DOCUMENTO: x]\nArt. 1º O imposto tem como fato gerador a prestação de serviços."


def ponto(pid, texto, documento, ordem, eixo=0):
    vetor = [0.0] * 1024
    vetor[eixo] = 1.0
    i, v = vetor_documento(texto)
    return models.PointStruct(
        id=pid,
        vector={DENSE: vetor, SPARSE: models.SparseVector(indices=i, values=v)},
        payload={"text": texto, "source": "Fonte", "document_id": documento, "ordem": ordem},
    )


def fonte(pid, texto):
    return Source(id=pid, text=texto, source="Fonte", score=0.8)


def store_com_pontos():
    client = QdrantClient(":memory:")
    settings = Settings()
    store = VectorStore(settings, client)
    store.ensure_collection()
    client.upsert(
        settings.collection_name,
        [
            ponto(1, CORTADO, "doc-a", 4),
            ponto(2, SEGUINTE, "doc-a", 5, eixo=3),
            ponto(3, "Outro documento:", "doc-b", 5),
            ponto(4, "Termina com ponto final.", "doc-a", 6),
        ],
    )
    return store


def test_continuacao_e_o_proximo_trecho_do_mesmo_documento():
    store = store_com_pontos()
    seguintes = store.continuacoes([1, 4, 999])
    assert {k: v.text for k, v in seguintes.items()} == {1: SEGUINTE}


def test_juntar_so_estende_trecho_que_termina_em_dois_pontos():
    cortado, completo = fonte(1, CORTADO), fonte(4, "Termina com ponto final.")
    juntos = juntar_continuacoes([cortado, completo], {1: fonte(2, SEGUINTE)})
    assert (
        juntos[0].text
        == CORTADO + "\nArt. 1º O imposto tem como fato gerador a prestação de serviços."
    )
    assert juntos[0].id == 1
    assert juntos[1] == completo


def test_sem_continuacao_mantem_o_trecho():
    cortado = fonte(1, CORTADO)
    assert juntar_continuacoes([cortado], {}) == [cortado]


class Store:
    def ensure_collection(self):
        pass

    def count(self):
        return 1

    def search_norms(self, vetor, chaves):
        return [], []

    def search_articles(self, vetor, pares):
        return []

    def search(self, vetor, pergunta):
        return [fonte(1, CORTADO)]

    def continuacoes(self, ids):
        return {1: fonte(2, SEGUINTE)} if 1 in ids else {}

    def close(self):
        pass


class Modelos:
    def __init__(self):
        self.fontes = None

    def embed_question(self, pergunta):
        return [1.0]

    def answer(self, pergunta, fontes, ausentes):
        self.fontes = fontes
        return "Resposta [1]"

    def close(self):
        pass


def test_servico_entrega_o_trecho_com_a_continuacao():
    modelos = Modelos()
    RagService(Settings(reranker_url=None), Store(), modelos).query("Qual é o fato gerador?")
    assert modelos.fontes[0].text.endswith("prestação de serviços.")


def store_com_janela():
    client = QdrantClient(":memory:")
    settings = Settings()
    store = VectorStore(settings, client)
    store.ensure_collection()
    client.upsert(
        settings.collection_name,
        [ponto(i, f"[H{i}]\nCorpo {i}", "doc-a", i, eixo=i) for i in range(1, 6)]
        + [ponto(9, "[H9]\nCorpo outro doc", "doc-b", 3)],
    )
    return store


def test_vizinhos_ficam_no_mesmo_documento_e_na_vizinhanca():
    viz = store_com_janela().vizinhos([3, 1, 999], raio=1)
    assert {d: f.id for d, f in viz[3].items()} == {-1: 2, 1: 4}
    assert {d: f.id for d, f in viz[1].items()} == {1: 2}
    assert 999 not in viz


def test_janela_prefere_seguinte_depois_anterior_e_respeita_o_limite():
    store = store_com_janela()
    base = fonte(3, "[H3]\nCorpo 3")
    viz = store.vizinhos([3], raio=2)
    um = expandir_janela([base], viz, 7)  # so cabe o seguinte (7 chars)
    assert um[0].text == "[H3]\nCorpo 3\nCorpo 4"
    dois = expandir_janela([base], viz, 14)
    assert dois[0].text == "[H3]\nCorpo 2\nCorpo 3\nCorpo 4"
    assert expandir_janela([base], viz, 0)[0].text == base.text


def test_janela_nao_repete_trecho_ja_escolhido():
    store = store_com_janela()
    a, b = fonte(3, "[H3]\nCorpo 3"), fonte(4, "[H4]\nCorpo 4")
    saida = expandir_janela([a, b], store.vizinhos([3, 4], raio=1), 100)
    assert saida[0].text == "[H3]\nCorpo 2\nCorpo 3"
    assert saida[1].text == "[H4]\nCorpo 4\nCorpo 5"


def test_janela_completa_continuacao_de_dois_pontos():
    store = store_com_pontos()
    cortado = fonte(1, CORTADO)
    saida = expandir_janela([cortado], store.vizinhos([1], raio=1), 5)
    assert (
        saida[0].text
        == CORTADO + "\nArt. 1º O imposto tem como fato gerador a prestação de serviços."
    )


class StoreJanela(Store):
    def vizinhos(self, ids, raio=2):
        return {1: {1: fonte(2, SEGUINTE)}}


def test_servico_com_janela_usa_vizinhos():
    modelos = Modelos()
    RagService(Settings(reranker_url=None, context_window_chars=500), StoreJanela(), modelos).query(
        "Qual é o fato gerador?"
    )
    assert modelos.fontes[0].text.endswith("prestação de serviços.")
