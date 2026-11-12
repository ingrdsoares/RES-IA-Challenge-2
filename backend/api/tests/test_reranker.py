import json

import httpx
from app.config import Settings
from app.rag import RagService
from app.reranker import Reranker
from app.schemas import Source


def fonte(texto: str, score: float = 0.8) -> Source:
    return Source(
        id=texto,
        source=f"{texto}.pdf",
        title=texto,
        document_id=texto,
        chunk_id="c0",
        score=score,
        text=texto,
    )


def reranker(handler, boost: float = 0.0) -> Reranker:
    return Reranker(
        Settings(reranker_url="http://reranker.test", rerank_legislation_boost=boost),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_ordena_pela_nota_sem_mudar_score_das_fontes():
    def handler(request):
        corpo = json.loads(request.content)
        assert corpo == {"question": "pergunta", "texts": ["a", "b", "c"]}
        return httpx.Response(200, json={"scores": [0.1, 0.9, 0.5]})

    saida = reranker(handler).reordenar("pergunta", [fonte("a"), fonte("b"), fonte("c")])

    assert [f.text for f in saida] == ["b", "c", "a"]
    assert all(f.score == 0.8 for f in saida)


def test_sem_url_nao_chama_ninguem_e_mantem_ordem():
    fontes = [fonte("a"), fonte("b")]

    assert Reranker(Settings(reranker_url=None)).reordenar("pergunta", fontes) == fontes


def test_lista_vazia_nao_chama_o_servico():
    def handler(request):
        raise AssertionError("não deveria chamar")

    assert reranker(handler).reordenar("pergunta", []) == []


def test_erros_mantem_a_ordem_da_busca():
    def fora_do_ar(request):
        raise httpx.ConnectError("recusado")

    def erro_500(request):
        return httpx.Response(500)

    def sem_json(request):
        return httpx.Response(200, text="<html>")

    def quantidade_errada(request):
        return httpx.Response(200, json={"scores": [0.9]})

    def nota_invalida(request):
        return httpx.Response(200, json={"scores": ["x", None]})

    def corpo_errado(request):
        return httpx.Response(200, json=[1, 2])

    fontes = [fonte("a"), fonte("b")]
    for handler in (fora_do_ar, erro_500, sem_json, quantidade_errada, nota_invalida, corpo_errado):
        assert reranker(handler).reordenar("pergunta", fontes) == fontes


def test_servico_reordena_candidatos_e_mantem_norma_citada_primeiro():
    citada = fonte("citada")
    ruim = fonte("ruim")
    boa = fonte("boa")

    class Store:
        def ensure_collection(self):
            pass

        def count(self):
            return 3

        def search_norms(self, vetor, chaves):
            return [citada], []

        def search(self, vetor, pergunta):
            return [ruim, boa]

        def search_articles(self, vetor, pares):
            return []

        def close(self):
            pass

    class Modelos:
        def embed_question(self, pergunta):
            return [1.0]

        def answer(self, pergunta, fontes, ausentes):
            return "Resposta [1]"

        def close(self):
            pass

    def handler(request):
        textos = json.loads(request.content)["texts"]
        assert textos == ["citada", "ruim", "boa"]
        return httpx.Response(200, json={"scores": [0.2, 0.1, 0.9]})

    servico = RagService(Settings(reranker_url=None), Store(), Modelos())
    servico.reranker = reranker(handler)

    resposta = servico.query("LC 87")

    assert [f.text for f in resposta.sources] == ["citada", "boa", "ruim"]


def _ordem_com_boost(notas, boost, leis=("lei",)):
    textos = ["lei", "sec"]
    fontes = [fonte(t) for t in textos]
    for f in fontes:
        f.natureza = "legislacao" if f.text in leis else "secundaria"

    def handler(request):
        return httpx.Response(200, json={"scores": notas})

    return [f.text for f in reranker(handler, boost).reordenar("p", fontes)]


def test_boost_zero_mantem_ordem_do_reranker():
    assert _ordem_com_boost([1.0, 1.2], 0.0) == ["sec", "lei"]


def test_boost_sobe_legislacao_ligeiramente_abaixo():
    # sigmoide(1.0)=0.73, sigmoide(1.2)=0.77: diferença < 0.1
    assert _ordem_com_boost([1.0, 1.2], 0.1) == ["lei", "sec"]


def test_boost_nao_supera_secundaria_muito_melhor():
    assert _ordem_com_boost([-3.0, 4.0], 0.1) == ["sec", "lei"]


def test_boost_sem_legislacao_nao_muda_ordem():
    assert _ordem_com_boost([1.0, 1.2], 0.5, leis=()) == ["sec", "lei"]


def test_sem_url_ignora_boost():
    fontes = [fonte("a"), fonte("b")]
    assert (
        Reranker(Settings(reranker_url=None, rerank_legislation_boost=0.5)).reordenar("p", fontes)
        == fontes
    )


def test_avisa_quando_sem_url(caplog):
    with caplog.at_level("WARNING"):
        Reranker(Settings())
    assert "RERANKER_URL" in caplog.text
