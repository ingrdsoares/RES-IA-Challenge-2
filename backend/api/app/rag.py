import re
from threading import Lock

from app.citacoes_normas import avisar_sem_suporte
from app.compostas import consultas_de_busca, partes_da_pergunta
from app.config import Settings
from app.errors import QueryBusy
from app.guardrails import e_recusa, pede_dados
from app.esclarecimento import caso_proprio, pedir_esclarecimento, texto_pedido
from app.models import LocalModels, citacoes_validas, prepare_sources
from app.normas import artigos_citados, chaves_normas
from app.reranker import Reranker
from app.schemas import QueryResponse, Source
from app.vector_store import VectorStore


def _corpo(fonte: Source) -> str:
    """Texto sem o cabeçalho do chunk, para reconhecer o mesmo trecho em pontos diferentes."""
    return " ".join(re.sub(r"\A\[[^\]]*\]\n", "", fonte.text).split())


def combinar(
    citados: list[Source], candidatos: list[Source], top_k: int, por_documento: int = 0
) -> list[Source]:
    """Norma citada primeiro, depois a busca; sem ponto ou corpo repetido.

    Com `por_documento` > 0, cada documento ocupa no máximo essa quantidade de vagas, para o
    top-k cobrir mais documentos; se faltar fonte, as excedentes voltam na ordem original.
    Trechos citados na pergunta sempre entram.
    """
    vistos: set[str] = set()
    unicos: list[Source] = []
    for fonte in citados + candidatos:
        corpo = _corpo(fonte)
        if corpo not in vistos:
            vistos.add(corpo)
            unicos.append(fonte)
    if not por_documento:
        return unicos[:top_k]
    ids_citados = {f.id for f in citados}
    contagem: dict[str | None, int] = {}
    saida: list[Source] = []
    sobras: list[Source] = []
    for fonte in unicos:
        doc = fonte.document_id or fonte.id
        if fonte.id in ids_citados or contagem.get(doc, 0) < por_documento:
            contagem[doc] = contagem.get(doc, 0) + 1
            saida.append(fonte)
        else:
            sobras.append(fonte)
    return (saida + sobras)[:top_k] if len(saida) < top_k else saida[:top_k]


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


def expandir_janela(fontes: list[Source], vizinhos: dict, janela: int) -> list[Source]:
    """Cada fonte ganha até `janela` caracteres de corpo dos trechos vizinhos do documento.

    Ordem de preferência: seguinte, anterior, 2º seguinte, 2º anterior... O anterior entra
    logo após o cabeçalho; o seguinte, no fim. Vizinho já escolhido (id ou corpo igual) é
    pulado. Fonte que termina em ":" recebe o seguinte inteiro, sem cortar.
    """
    ja = {f.id for f in fontes}
    corpos = {_corpo(f) for f in fontes}
    saida = []
    for fonte in fontes:
        viz = vizinhos.get(fonte.id) or {}
        restante = janela
        antes, depois = [], []
        for n in range(1, max(map(abs, viz), default=0) + 1):
            for delta in (n, -n):
                v = viz.get(delta)
                if v is None or v.id in ja or restante <= 0:
                    continue
                corpo = _corpo_bruto(v)
                if not corpo or _corpo(v) in corpos:
                    continue
                if not (delta == 1 and fonte.text.rstrip().endswith(":")):
                    corpo = corpo[:restante]
                restante -= len(corpo)
                corpos.add(_corpo(v))
                (depois if delta > 0 else antes).append((delta, corpo))
        if antes or depois:
            cabecalho = re.match(r"\A\[[^\]]*\]\n", fonte.text)
            cabecalho = cabecalho.group(0) if cabecalho else ""
            corpo = fonte.text[len(cabecalho) :].rstrip()
            partes = [c for _, c in sorted(antes)] + [corpo] + [c for _, c in sorted(depois)]
            fonte = fonte.model_copy(update={"text": cabecalho + "\n".join(partes)})
        saida.append(fonte)
    return saida


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
            if pedido := pedir_esclarecimento(question):
                return QueryResponse(status="needs_clarification", answer=pedido, sources=[])
            if self.settings.esclarecimento_modelo and caso_proprio(question):
                if faltam := self.models.dados_faltantes(question):
                    return QueryResponse(
                        status="needs_clarification", answer=texto_pedido(faltam), sources=[]
                    )
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
            sources, ausentes = self._contexto(question, vector)
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
            if self.settings.guardrails_texto:
                if e_recusa(answer) and self.settings.retry_recusa:
                    sources, answer = self._tentar_ampliado(question, vector, sources, answer)
                if e_recusa(answer):
                    return QueryResponse(
                        status="insufficient_context",
                        answer=(
                            "Não há contexto suficiente na base "
                            "para fundamentar uma resposta à pergunta."
                        ),
                        sources=sources,
                    )
                if pede_dados(answer):
                    return QueryResponse(status="needs_clarification", answer=answer, sources=[])
            if self.settings.conferir_citacoes:
                answer, _ = avisar_sem_suporte(answer, sources)
            return QueryResponse(status="answered", answer=answer, sources=sources)
        finally:
            self._query_lock.release()

    def _contexto(self, question: str, vector: list[float]):
        """Fontes escolhidas para a pergunta (já cortadas ao orçamento) e normas ausentes."""
        citados, ausentes = self.store.search_norms(vector, chaves_normas(question))
        citados = self.store.search_articles(vector, artigos_citados(question)) + citados
        candidatos = combinar([], citados + self.store.search(vector, question), 1000)
        ordem = self.reranker.reordenar(question, candidatos)
        escolhidos = combinar(
            citados,
            ordem[:2] + self._por_parte(question) + ordem,
            self.settings.top_k,
            self.settings.max_trechos_por_documento,
        )
        if self.settings.context_window_chars:
            vizinhos = self.store.vizinhos([f.id for f in escolhidos])
            escolhidos = expandir_janela(escolhidos, vizinhos, self.settings.context_window_chars)
        else:
            cortados = [f.id for f in escolhidos if f.text.rstrip().endswith(":")]
            seguintes = self.store.continuacoes(cortados) if cortados else {}
            escolhidos = juntar_continuacoes(escolhidos, seguintes)
        sources = prepare_sources(
            escolhidos,
            self.settings.max_context_chars,
            question=question,
            num_ctx=self.settings.num_ctx,
            num_predict=self.settings.num_predict,
        )
        return sources, ausentes

    def _tentar_ampliado(self, question, vector, sources, answer):
        """Uma segunda tentativa com busca ampliada antes de aceitar a recusa do modelo."""
        original = self.settings
        ampliado = original.model_copy(
            update={"candidate_k": max(original.candidate_k, 100), "top_k": 10}
        )
        self.settings = self.store.settings = ampliado
        try:
            novas, ausentes = self._contexto(question, vector)
        finally:
            self.settings = self.store.settings = original
        if not novas:
            return sources, answer
        nova, _ = citacoes_validas(self.models.answer(question, novas, ausentes), len(novas))
        return (sources, answer) if e_recusa(nova) else (novas, nova)

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
