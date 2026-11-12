from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.errors import DependencyUnavailable, QueryBusy
from qdrant_client import models


def add_document(service, text="Texto de teste", vector=None):
    service.store.client.upsert(
        "knowledge_base",
        [
            models.PointStruct(
                id=1,
                vector={"dense": vector or [1.0] + [0.0] * 1023},
                payload={"text": text, "source": "Manual de teste"},
            )
        ],
    )


def test_empty_collection_does_not_use_models(service, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Empty collection must not call Ollama")

    monkeypatch.setattr(service.models, "embed_question", forbidden)
    monkeypatch.setattr(service.models, "answer", forbidden)
    response = service.query("Pergunta")
    assert response.status == "empty_knowledge_base"
    assert response.sources == []
    assert response.answer


def test_no_relevant_results_skips_generation(service, monkeypatch):
    add_document(service, vector=[0.0, 1.0] + [0.0] * 1022)

    def forbidden(*args, **kwargs):
        pytest.fail("Irrelevant context must not call generation")

    monkeypatch.setattr(service.models, "answer", forbidden)
    response = service.query("Pergunta")
    assert response.status == "insufficient_context"
    assert response.sources == []


def test_complete_rag_returns_only_bounded_context(service):
    add_document(service, "🎉" * 6000)
    response = service.query("Pergunta")
    assert response.status == "answered"
    assert response.answer == "Orientação [1]"
    assert response.sources[0].id == 1
    assert 0 < len(response.sources[0].text) < 4000


def test_query_failure_releases_lock(service, monkeypatch):
    original = service.store.count

    def unavailable():
        raise DependencyUnavailable("Offline")

    monkeypatch.setattr(service.store, "count", unavailable)
    with pytest.raises(DependencyUnavailable):
        service.query("Pergunta")
    monkeypatch.setattr(service.store, "count", original)
    assert service.query("Pergunta").status == "empty_knowledge_base"


def test_concurrent_query_is_rejected_without_waiting(service, monkeypatch):
    entered, release = Event(), Event()
    original = service.store.count

    def blocked():
        entered.set()
        assert release.wait(5)
        return original()

    monkeypatch.setattr(service.store, "count", blocked)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(service.query, "Primeira")
        try:
            assert entered.wait(5)
            with pytest.raises(QueryBusy):
                service.query("Segunda")
        finally:
            release.set()
        assert first.result(timeout=5).status == "empty_knowledge_base"


def test_pergunta_de_caso_sem_dados_pede_esclarecimento_sem_modelos(service, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Esclarecimento não deve consultar a base nem o Ollama")

    monkeypatch.setattr(service.store, "count", forbidden)
    monkeypatch.setattr(service.models, "embed_question", forbidden)
    monkeypatch.setattr(service.models, "answer", forbidden)
    response = service.query("Minha empresa pode entrar no Simples?")
    assert response.status == "needs_clarification"
    assert response.sources == []
    assert "CNAE" in response.answer


def test_filtro_com_modelo_pede_dados_antes_da_busca(service, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pedido de dados não deve consultar a base")

    service.settings = service.settings.model_copy(update={"esclarecimento_modelo": True})
    monkeypatch.setattr(service.models, "dados_faltantes", lambda q: ["o CNAE", "a receita"])
    monkeypatch.setattr(service.store, "count", forbidden)
    response = service.query("Sou dentista, posso abrir uma empresa no Simples?")
    assert response.status == "needs_clarification"
    assert "- o CNAE" in response.answer


def test_filtro_com_modelo_desligado_ou_pergunta_geral_nao_chama_o_modelo(service, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Filtro com modelo não deveria rodar")

    monkeypatch.setattr(service.models, "dados_faltantes", forbidden)
    assert service.query("Sou dentista, posso abrir uma empresa?").status != "needs_clarification"
    service.settings = service.settings.model_copy(update={"esclarecimento_modelo": True})
    assert service.query("Qual é o limite do MEI?").status != "needs_clarification"
