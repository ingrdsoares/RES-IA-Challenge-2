import logging
import re
from threading import Lock

from app.config import Settings
from app.errors import QueryBusy
from app.ferramentas import PlanejadorBuscas, intercalar
from app.models import LocalModels, citacoes_validas, prepare_sources
from app.normas import artigos_citados, chave_artigo, chaves_normas
from app.reranker import Reranker
from app.schemas import QueryResponse, Source
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)


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
            sources = prepare_sources(
                combinar(citados, self._recuperar(question, vector, citados), self.settings.top_k),
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

    def _recuperar(self, question: str, vector: list[float], citados: list[Source]) -> list[Source]:
        if self.settings.tool_calling:
            try:
                planejador = PlanejadorBuscas(self.models.planejar, self._executar_ferramenta)
                grupos = planejador.coletar(question).grupos
            except Exception:
                logger.warning("Planejamento de buscas falhou; usando a busca atual", exc_info=True)
                grupos = []
            if grupos:
                return intercalar(grupos)
        candidatos = combinar([], citados + self.store.search(vector, question), 1000)
        return self.reranker.reordenar(question, candidatos)

    def _executar_ferramenta(self, nome: str, args: dict) -> list[Source]:
        consulta = args.get("consulta") or f"{args['norma']} art. {args.get('artigo', '')}"
        vetor = self.models.embed_question(consulta)
        if nome == "busca_geral":
            achados = self.store.search(vetor, consulta)
        else:
            chaves = chaves_normas(args["norma"])
            if nome == "buscar_artigo":
                artigo = chave_artigo(f"art. {args['artigo'].removeprefix('art. ')}")
                achados = self.store.search_articles(vetor, [(c, artigo) for c in chaves])
            else:
                achados = self.store.search_norms(vetor, chaves)[0]
        return self.reranker.reordenar(consulta, combinar([], achados, 1000))

    def ready(self) -> None:
        self.store.ensure_collection()
        self.models.check_models()

    def close(self) -> None:
        try:
            self.store.close()
        finally:
            self.reranker.close()
            self.models.close()
