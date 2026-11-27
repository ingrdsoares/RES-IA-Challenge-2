import json
import math
import re
from collections.abc import Sequence

import httpx
import ollama

from app.config import Settings
from app.errors import DependencyUnavailable, dependency_errors
from app.llm_client import chat
from app.normas import nome_norma
from app.prompt_management import PromptUnavailable, load_prompt, observation, prompt_scope, traced
from app.schemas import Source

AVISO_CITACAO = "\n\n(Citações sem fonte correspondente foram removidas desta resposta.)"
_FORMATO_ESCLARECIMENTO = {
    "type": "object",
    "properties": {
        "precisa_dados": {"type": "boolean"},
        "faltam": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
    },
    "required": ["precisa_dados", "faltam"],
}


def citacoes_validas(texto: str, total: int) -> tuple[str, bool]:
    """Tira [n] sem fonte correspondente e avisa; o modelo não comprova a própria citação."""
    removidas = False

    def trocar(match: re.Match) -> str:
        nonlocal removidas
        if 1 <= int(match.group(1)) <= total:
            return match.group(0)
        removidas = True
        return ""

    limpo = re.sub(r"\[(\d+)\]", trocar, texto)
    if not removidas:
        return texto, False
    limpo = re.sub(r"(?:,\s*)+(?=[,.;\s]*(?:\n|$))|[ \t]+(?=[,.;])", "", limpo).strip()
    return limpo + AVISO_CITACAO, True


def _messages(
    question: str, sources: list[Source], system: str, ausentes: Sequence[str] = ()
) -> tuple[list[dict[str, str]], dict[str, str]]:
    missing = (
        load_prompt("rag/missing-source", names=", ".join(nome_norma(chave) for chave in ausentes))
        if ausentes
        else None
    )
    documents = [
        {
            "citation": f"[{i}]",
            "text": s.text,
            "source": s.source,
            "title": s.title,
            "reference_date": str(s.reference_date) if s.reference_date else None,
            "effective_date": str(s.effective_date) if s.effective_date else None,
        }
        for i, s in enumerate(sources, 1)
    ]
    request = load_prompt(
        "rag/question",
        documents=json.dumps(documents, ensure_ascii=False),
        question=question,
        missing=missing.text if missing else "",
    )
    versions = {"rag/question": request.version}
    if missing:
        versions["rag/missing-source"] = missing.version
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": request.text},
    ], versions


def _prompt_size(messages: list[dict[str, str]]) -> int:
    # Estimativa conservadora de 2 bytes por token para texto legal.
    return sum(len(m["content"].encode("utf-8")) for m in messages) // 2


@prompt_scope()
def prepare_sources(
    sources: list[Source],
    max_chars: int,
    *,
    question: str | None = None,
    num_ctx: int = 8192,
    num_predict: int = 1024,
) -> list[Source]:
    if not sources or max_chars <= 0:
        return []
    system = load_prompt("rag/answer").text if question is not None else ""
    selected: list[Source] = []
    remaining = max_chars
    for source in sources:
        if remaining <= 0:
            break
        limit = min(len(source.text), remaining)
        if question is not None:
            low, high = 0, limit
            while low < high:
                mid = (low + high + 1) // 2
                candidate = source.model_copy(update={"text": source.text[:mid]})
                messages, _ = _messages(question, selected + [candidate], system)
                if _prompt_size(messages) <= num_ctx - num_predict - 256:
                    low = mid
                else:
                    high = mid - 1
            limit = low
        text = source.text[:limit].strip()
        if text:
            selected.append(source.model_copy(update={"text": text}))
            remaining -= limit
    return selected


class LocalModels:
    def __init__(
        self,
        settings: Settings,
        client: ollama.Client | None = None,
        http_client: httpx.Client | None = None,
        embedding_client: httpx.Client | None = None,
    ):
        self.settings = settings
        # Embeddings pelo serviço próprio quando EMBEDDING_URL existe; senão, pelo Ollama.
        self.embedding_client = embedding_client or (
            httpx.Client(base_url=str(settings.embedding_url), timeout=settings.embedding_timeout)
            if settings.embedding_url
            else None
        )
        # Só para geração na nuvem (LLM_PROVIDER google/deepseek).
        self.http_client = http_client or (
            httpx.Client(timeout=settings.ollama_timeout)
            if settings.llm_provider != "ollama"
            else None
        )
        self.client = (
            client
            if client is not None
            else ollama.Client(
                host=str(settings.ollama_url),
                timeout=settings.ollama_timeout,
            )
        )

    def check_models(self) -> None:
        required = set()
        if self.embedding_client is not None:
            with dependency_errors("Serviço de embeddings"):
                self.embedding_client.get("/health").raise_for_status()
        else:
            required.add(self.settings.embedding_model)
        if self.settings.llm_provider == "ollama":
            required.add(self.settings.generation_model)
        if not required:
            return
        with dependency_errors("Ollama"):
            available = {item.model for item in self.client.list().models}
        if not required <= available:
            raise DependencyUnavailable("Os modelos configurados não estão instalados no Ollama.")

    def _embed(self, text: str, **ollama_options) -> list[float]:
        if self.embedding_client is not None:
            with dependency_errors("Serviço de embeddings"):
                response = self.embedding_client.post("/embed", json={"texts": [text]})
                response.raise_for_status()
                vectors = response.json().get("embeddings") or []
            service = "serviço de embeddings"
        else:
            with dependency_errors("Ollama"):
                vectors = self.client.embed(
                    model=self.settings.embedding_model,
                    input=text,
                    truncate=False,
                    **ollama_options,
                ).embeddings
            service = "Ollama"
        vector = vectors[0] if len(vectors) == 1 else []
        if (
            len(vector) != self.settings.embedding_dimensions
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vector)
            or not any(vector)
        ):
            raise DependencyUnavailable(f"Embedding inválido retornado pelo {service}.")
        return list(vector)

    def embed_question(self, question: str) -> list[float]:
        # Uma pergunta leva 0,1 s na CPU; no Ollama, a GPU fica livre para a geração.
        prompt = load_prompt("rag/embedding-query", question=question)
        with observation(
            "rag.embedding",
            as_type="embedding",
            model=self.settings.embedding_model,
            metadata={"prompt_versions": {"rag/embedding-query": prompt.version}},
        ):
            return self._embed(prompt.text, options={"num_gpu": 0})

    def embed_document(self, text: str) -> list[float]:
        """Trechos indexados vão sem a instrução de consulta (modelo assimétrico)."""
        return self._embed(text)

    @traced("rag.answer")
    def answer(self, question: str, sources: list[Source], ausentes: Sequence[str] = ()) -> str:
        prompt = load_prompt("rag/answer")
        messages, versions = _messages(question, sources, prompt.text, ausentes)
        if (
            not sources
            or _prompt_size(messages) > self.settings.num_ctx - self.settings.num_predict - 256
        ):
            raise DependencyUnavailable("O contexto ultrapassa o limite configurado para geração.")
        content = chat(
            self.settings,
            messages,
            prompt=prompt,
            prompt_versions=versions,
            max_tokens=self.settings.num_predict,
            ollama_client=self.client,
            http_client=self.http_client,
        ).texto
        if not content or not content.strip():
            raise DependencyUnavailable("O modelo não retornou uma resposta utilizável.")
        return content.strip()

    def dados_faltantes(self, question: str) -> list[str]:
        """Dados do caso que faltam para responder, segundo o modelo; [] se não faltam.

        Qualquer falha (Ollama fora, JSON inválido) devolve [] e a pergunta segue para a busca:
        este filtro nunca impede uma resposta por erro próprio.
        """
        prompt = load_prompt("rag/clarification")
        try:
            resposta = chat(
                self.settings,
                [
                    {"role": "system", "content": prompt.text},
                    {"role": "user", "content": question},
                ],
                prompt=prompt,
                max_tokens=1024 if self.settings.esclarecimento_raciocinio else 128,
                schema=_FORMATO_ESCLARECIMENTO,
                think=self.settings.esclarecimento_raciocinio,
                num_ctx=2048,
                ollama_client=self.client,
                http_client=self.http_client,
            )
            dados = json.loads(resposta.texto)
        except PromptUnavailable:
            raise
        except (
            DependencyUnavailable,
            ollama.ResponseError,
            httpx.HTTPError,
            ConnectionError,
            ValueError,
            TypeError,
            AttributeError,
        ):
            return []
        if not isinstance(dados, dict) or dados.get("precisa_dados") is not True:
            return []
        faltam = dados.get("faltam")
        if not isinstance(faltam, list):
            return []
        return [str(f).strip() for f in faltam if str(f).strip()][:4]

    def close(self) -> None:
        self.client.close()
        if self.http_client is not None:
            self.http_client.close()
        if self.embedding_client is not None:
            self.embedding_client.close()
