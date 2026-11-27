"""Topologias de comparação LLM x RAG para o relatório da Semana 3.

Escolhidas por `TOPOLOGIA` em `python -m evaluation` (ver __main__.py):
  llm_pura     LLM sem nenhum contexto recuperado
  rag_sem_llm  busca densa top-3 devolvida num modelo fixo, sem LLM
  naive_rag    busca densa top-k + LLM, sem esparsa, sem reranker e sem busca por norma citada
Sem TOPOLOGIA, vale o sistema completo (RAG híbrido com reranker).
"""

import os

from app.errors import dependency_errors
from app.llm_client import chat
from app.models import prepare_sources
from app.prompt_management import load_prompt, traced
from app.schemas import QueryResponse

from evaluation.adapter import InternalRagClient

SEM_CONTEXTO = QueryResponse(
    status="insufficient_context",
    answer="Não há contexto suficiente na base para fundamentar uma resposta à pergunta.",
    sources=[],
)


class TopologiaClient(InternalRagClient):
    def __init__(self, topologia: str):
        super().__init__()
        self.topologia = topologia

    def _densa(self, question, limite):
        vector = self.service.models.embed_question(question)
        with dependency_errors("Qdrant"):
            hits = self.service.store._densa(vector, limite)
        return self.service.store._fontes(hits)

    @traced("evaluation.topology")
    def query(self, question):
        s = self.settings
        if self.topologia == "llm_pura":
            prompt = load_prompt("evaluation/llm-only")
            response = chat(
                s.model_copy(update={"llm_provider": "ollama"}),
                [
                    {"role": "system", "content": prompt.text},
                    {"role": "user", "content": question},
                ],
                prompt=prompt,
                max_tokens=s.num_predict,
                ollama_client=self.service.models.client,
            )
            return QueryResponse(status="answered", answer=response.texto.strip(), sources=[])
        if self.topologia == "rag_sem_llm":
            fontes = self._densa(question, 3)
            if not fontes:
                return SEM_CONTEXTO
            blocos = [f"[{i}] {f.text.strip()}" for i, f in enumerate(fontes, 1)]
            return QueryResponse(
                status="answered",
                answer="Trechos mais relevantes da base:\n\n" + "\n\n".join(blocos),
                sources=fontes,
            )
        if self.topologia == "naive_rag":
            fontes = prepare_sources(
                self._densa(question, s.top_k),
                s.max_context_chars,
                question=question,
                num_ctx=s.num_ctx,
                num_predict=s.num_predict,
            )
            if not fontes:
                return SEM_CONTEXTO
            return QueryResponse(
                status="answered",
                answer=self.service.models.answer(question, fontes),
                sources=fontes,
            )
        raise ValueError(f"topologia desconhecida: {self.topologia}")


def fabrica():
    nome = os.environ.get("TOPOLOGIA", "").strip()
    return (lambda: TopologiaClient(nome)) if nome else None
