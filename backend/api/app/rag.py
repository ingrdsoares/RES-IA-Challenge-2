import re
from threading import Lock

from app.compostas import consultas_de_busca, partes_da_pergunta
from app.config import Settings
from app.errors import QueryBusy
from app.models import LocalModels, citacoes_validas, prepare_sources
from app.normas import artigos_citados, chaves_normas
from app.reranker import Reranker
from app.schemas import QueryResponse, Source
from app.vector_store import VectorStore


def _corpo(fonte: Source) -> str:
    """Texto sem o cabeçalho do chunk, para reconhecer o mesmo trecho em pontos diferentes."""
    return " ".join(re.sub(r"\A\[[^\]]*\]\n", "", fonte.text).split())


def combinar(citados: list[Source], candidatos: list[Source], top_k: int) -> list[Source]:
    """Norma citada primeiro, depois a busca; sem ponto ou corpo repetido."""
    vistos: set[str] = set()
    saida: list[Source] = []
    for fonte in citados + candidatos:
        corpo = _corpo(fonte)
        if corpo not in vistos:
            vistos.add(corpo)
            saida.append(fonte)
    return saida[:top_k]


def juntar_continuacoes(fontes: list[Source], seguintes: dict) -> list[Source]:
    """Trecho que termina em dois-pontos recebe o corpo do trecho seguinte do documento."""
    saida = []
    for fonte in fontes:
        seguinte = seguintes.get(fonte.id)
        if seguinte and fonte.text.rstrip().endswith(":"):
            texto = fonte.text.rstrip() + "\n" + _corpo_bruto(seguinte)
            fonte = fonte.model_copy(update={"text": texto})
        saida.append(fonte)
    return saida


def _corpo_bruto(fonte: Source) -> str:
    return re.sub(r"\A\[[^\]]*\]\n", "", fonte.text).strip()


class RagService:
    def __init__(self, settings: Settings, store: VectorStore, models: LocalModels):
        self.settings = settings
        self.store = store
        self.models = models
        self.reranker = Reranker(settings)
        self._query_lock = Lock()

    def query(self, question: str) -> QueryResponse:
        if not self._query_lock.acquire(blocking=False):
            raise QueryBusy()
        try:
            self.store.ensure_collection()
            if self.store.count() == 0:
                return QueryResponse(
                    status="empty_knowledge_base",
                    answer=(
                        "A base de conhecimento está vazia. "
                        "Adicione documentos para consultar o RAG."
                    ),
                    sources=[],
                )
            vector = self.models.embed_question(question)
            citados, ausentes = self.store.search_norms(vector, chaves_normas(question))
            citados = self.store.search_articles(vector, artigos_citados(question)) + citados
            candidatos = combinar([], citados + self.store.search(vector, question), 1000)
            ordem = self.reranker.reordenar(question, candidatos)
            escolhidos = combinar(
                citados, ordem[:2] + self._por_parte(question) + ordem, self.settings.top_k
            )
            cortados = [f.id for f in escolhidos if f.text.rstrip().endswith(":")]
            seguintes = self.store.continuacoes(cortados) if cortados else {}
            sources = prepare_sources(
                juntar_continuacoes(escolhidos, seguintes),
                self.settings.max_context_chars,
                question=question,
                num_ctx=self.settings.num_ctx,
                num_predict=self.settings.num_predict,
            )
            if not sources:
                return QueryResponse(
                    status="insufficient_context",
                    answer=(
                        "Não há contexto suficiente na base "
                        "para fundamentar uma resposta à pergunta."
                    ),
                    sources=[],
                )
            answer, _ = citacoes_validas(
                self.models.answer(question, sources, ausentes), len(sources)
            )
            return QueryResponse(status="answered", answer=answer, sources=sources)
        finally:
            self._query_lock.release()

    def _por_parte(self, question: str) -> list[Source]:
        """Em pergunta composta, os melhores trechos de cada parte, alternados."""
        consultas = consultas_de_busca(partes_da_pergunta(question))
        if len(consultas) < 2:
            return []
        grupos = []
        for consulta in consultas:
            achados = self.store.search(self.models.embed_question(consulta), consulta)
            grupos.append(self.reranker.reordenar(consulta, combinar([], achados, 1000)))
        alternados: list[Source] = []
        for i in range(max(len(g) for g in grupos)):
            alternados += [g[i] for g in grupos if i < len(g)]
        return alternados

    def ready(self) -> None:
        self.store.ensure_collection()
        self.models.check_models()

    def close(self) -> None:
        try:
            self.store.close()
        finally:
            self.reranker.close()
            self.models.close()
