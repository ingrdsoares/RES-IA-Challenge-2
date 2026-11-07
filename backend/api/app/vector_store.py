import logging

from pydantic import ValidationError
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import Settings
from app.errors import CollectionIncompatible, dependency_errors
from app.schemas import Source
from app.sparse import vetor_consulta

logger = logging.getLogger(__name__)

DENSE = "dense"
SPARSE = "sparse"
RRF_K = 60


class VectorStore:
    def __init__(self, settings: Settings, client: QdrantClient | None = None):
        self.settings = settings
        self.client = (
            client
            if client is not None
            else QdrantClient(
                url=str(settings.qdrant_url),
                timeout=settings.qdrant_timeout,
            )
        )

    def ensure_collection(self) -> None:
        with dependency_errors("Qdrant"):
            if not self.client.collection_exists(self.settings.collection_name):
                try:
                    self.client.create_collection(
                        collection_name=self.settings.collection_name,
                        vectors_config={
                            DENSE: models.VectorParams(
                                size=self.settings.embedding_dimensions,
                                distance=models.Distance.COSINE,
                            )
                        },
                        sparse_vectors_config={
                            SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)
                        },
                    )
                except UnexpectedResponse as exc:
                    if exc.status_code != 409:
                        raise
            params = self.client.get_collection(self.settings.collection_name).config.params
            dense = params.vectors.get(DENSE) if isinstance(params.vectors, dict) else None
            if (
                dense is None
                or dense.size != self.settings.embedding_dimensions
                or dense.distance != models.Distance.COSINE
                or SPARSE not in (params.sparse_vectors or {})
            ):
                raise CollectionIncompatible("A coleção vetorial tem configuração incompatível.")

    def count(self) -> int:
        with dependency_errors("Qdrant"):
            return self.client.count(self.settings.collection_name, exact=True).count

    def _fontes(self, hits) -> list[Source]:
        sources = []
        for hit in hits:
            try:
                sources.append(
                    Source.model_validate(
                        (hit.payload or {}) | {"id": hit.id, "score": hit.score},
                    )
                )
            except ValidationError:
                logger.warning("Trecho %s descartado: payload inválido", hit.id)
        return sources

    def _densa(self, vector: list[float], limit: int, filtro=None, limiar=True):
        return self.client.query_points(
            collection_name=self.settings.collection_name,
            query=vector,
            using=DENSE,
            limit=limit,
            query_filter=filtro,
            score_threshold=self.settings.score_threshold if limiar else None,
            with_payload=True,
        ).points

    def _esparsa(self, question: str, limit: int):
        indices, valores = vetor_consulta(question)
        if not indices:
            return []
        try:
            return self.client.query_points(
                collection_name=self.settings.collection_name,
                query=models.SparseVector(indices=indices, values=valores),
                using=SPARSE,
                limit=limit,
                with_payload=False,
            ).points
        except Exception:
            logger.warning("Busca esparsa indisponível; usando só a densa", exc_info=True)
            return []

    def search(self, vector: list[float], question: str = "") -> list[Source]:
        """Candidatos por RRF de densa e esparsa, com o cosseno real em `score`.

        Trecho só da esparsa passa pelo mesmo limiar: sem isso, a pergunta fora do acervo
        deixaria de cair em contexto insuficiente.
        """
        limite = self.settings.candidate_k
        with dependency_errors("Qdrant"):
            densos = self._densa(vector, limite)
            esparsos = self._esparsa(question, limite)
            por_id = {hit.id: hit for hit in densos}
            so_esparsos = [hit.id for hit in esparsos if hit.id not in por_id]
            if so_esparsos:
                filtro = models.Filter(must=[models.HasIdCondition(has_id=so_esparsos)])
                por_id |= {h.id: h for h in self._densa(vector, len(so_esparsos), filtro)}
        rrf: dict = {}
        for lista in (densos, esparsos):
            for posicao, hit in enumerate(lista, 1):
                if hit.id in por_id:
                    rrf[hit.id] = rrf.get(hit.id, 0.0) + 1 / (RRF_K + posicao)
        ordem = sorted(rrf, key=lambda pid: rrf[pid], reverse=True)
        return self._fontes(por_id[pid] for pid in ordem)

    def search_norms(
        self, vector: list[float], chaves: list[str]
    ) -> tuple[list[Source], list[str]]:
        """Melhores trechos de cada norma citada e as chaves que não existem no acervo."""
        achados: list[Source] = []
        ausentes: list[str] = []
        limite = self.settings.citation_slots
        limiar = self.settings.score_threshold
        with dependency_errors("Qdrant"):
            for chave in chaves:
                filtro = models.Filter(
                    must=[models.FieldCondition(key="norma", match=models.MatchValue(value=chave))]
                )
                hits = self._densa(vector, limite, filtro, limiar=False)
                if not hits:
                    ausentes.append(chave)
                achados += self._fontes(h for h in hits if h.score >= limiar)
        return achados, ausentes

    def close(self) -> None:
        self.client.close()
