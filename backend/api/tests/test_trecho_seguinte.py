from app.config import Settings
from app.rag import RagService, juntar_continuacoes
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
