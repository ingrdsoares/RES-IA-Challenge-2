import pytest
from app.config import Settings
from app.normas import artigos_citados, chave_artigo
from app.sparse import vetor_documento
from app.vector_store import DENSE, SPARSE, VectorStore
from qdrant_client import QdrantClient, models


@pytest.mark.parametrize(
    ("rotulo", "chave"),
    [
        ("Art. 23", "23"),
        ("Art. 18-A", "18-a"),
        ("art. 8º-A", "8-a"),
        ("Art. 1º", "1"),
        ("Geral", None),
    ],
)
def test_chave_artigo(rotulo, chave):
    assert chave_artigo(rotulo) == chave


@pytest.mark.parametrize(
    ("pergunta", "esperado"),
    [
        ("O que o art. 23 da LC 87 diz?", [("lc:87", "23")]),
        ("Segundo o artigo 13-A da Lei Complementar 123?", [("lc:123", "13-a")]),
        ("O art. 138 do CTN?", [("lei:5172", "138")]),
        ("Pela LC 116, o que diz o art. 7º?", [("lc:116", "7")]),
        ("O art. 7º da LC 116 e o art. 23 da LC 87?", [("lc:116", "7"), ("lc:87", "23")]),
        ("O que diz a LC 87?", []),
        ("O que diz o art. 23?", []),
    ],
)
def test_artigos_citados(pergunta, esperado):
    assert artigos_citados(pergunta) == esperado


def ponto(pid, eixo, texto, norma, artigo):
    vetor = [0.0] * 1024
    vetor[eixo] = 1.0
    i, v = vetor_documento(texto)
    return models.PointStruct(
        id=pid,
        vector={DENSE: vetor, SPARSE: models.SparseVector(indices=i, values=v)},
        payload={"text": texto, "source": "Fonte", "norma": [norma], "artigo": artigo},
    )


def test_busca_traz_o_artigo_mesmo_longe_da_pergunta_e_ignora_ausente():
    client = QdrantClient(":memory:")
    settings = Settings()
    store = VectorStore(settings, client)
    store.ensure_collection()
    client.upsert(
        settings.collection_name,
        [
            ponto(1, 0, "Texto parecido com a pergunta", "lc:87", "13"),
            ponto(2, 5, "O direito extingue-se em cinco anos", "lc:87", "23"),
            ponto(3, 5, "Outra norma com mesmo número", "lc:123", "23"),
        ],
    )
    vetor = [0.0] * 1024
    vetor[0] = 1.0

    achados = store.search_articles(vetor, [("lc:87", "23"), ("lc:87", "999")])

    assert [f.text for f in achados] == ["O direito extingue-se em cinco anos"]
    client.close()
