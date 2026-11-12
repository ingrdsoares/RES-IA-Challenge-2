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
NATUREZA_NORMA = "legislacao"


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
        indices, valores = vetor_consulta(question, self.settings.peso_expansao)
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

        A legislação recebe reforço (`legislation_boost`) sobre soluções de consulta e FAQs que
        repetem a mesma regra.

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
        for pid in rrf:
            if (por_id[pid].payload or {}).get("natureza") == NATUREZA_NORMA:
                rrf[pid] *= 1 + self.settings.legislation_boost
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

    def search_articles(self, vector: list[float], pares: list[tuple[str, str]]) -> list[Source]:
        """Trechos dos artigos citados, mesmo longe da pergunta; artigo ausente é ignorado."""
        achados: list[Source] = []
        with dependency_errors("Qdrant"):
            for norma, artigo in pares:
                filtro = models.Filter(
                    must=[
                        models.FieldCondition(key="norma", match=models.MatchValue(value=norma)),
                        models.FieldCondition(key="artigo", match=models.MatchValue(value=artigo)),
                    ]
                )
                achados += self._fontes(
                    self._densa(vector, self.settings.citation_slots, filtro, limiar=False)
                )
        return achados

    def continuacoes(self, ids: list) -> dict:
        """Para cada ponto, o trecho seguinte do mesmo documento, pelo campo ordem."""
        seguintes: dict = {}
        with dependency_errors("Qdrant"):
            pontos = self.client.retrieve(
                self.settings.collection_name, ids, with_payload=["document_id", "ordem"]
            )
            for p in pontos:
                documento, ordem = (
                    (p.payload or {}).get("document_id"),
                    (p.payload or {}).get("ordem"),
                )
                if documento is None or ordem is None:
                    continue
                filtro = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=documento)
                        ),
                        models.FieldCondition(
                            key="ordem", match=models.MatchValue(value=ordem + 1)
                        ),
                    ]
                )
                achados, _ = self.client.scroll(
                    self.settings.collection_name, filtro, limit=1, with_payload=True
                )
                fontes = self._fontes(
                    models.ScoredPoint(id=a.id, version=0, score=0.0, payload=a.payload)
                    for a in achados
                )
                if fontes:
                    seguintes[p.id] = fontes[0]
        return seguintes

    def vizinhos(self, ids: list, raio: int = 2) -> dict:
        """Por ponto, os trechos até `raio` posições antes e depois no MESMO documento.

        Devolve {id: {delta: Source}}, delta = ordem do vizinho - ordem do ponto (sem 0).
        Uma leitura por id e uma única busca filtrada para todos os pontos.
        """
        with dependency_errors("Qdrant"):
            pontos = self.client.retrieve(
                self.settings.collection_name, ids, with_payload=["document_id", "ordem"]
            )
            origem = {
                p.id: (p.payload["document_id"], p.payload["ordem"])
                for p in pontos
                if (p.payload or {}).get("document_id") is not None
                and (p.payload or {}).get("ordem") is not None
            }
            if not origem:
                return {}
            filtro = models.Filter(
                should=[
                    models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id", match=models.MatchValue(value=doc)
                            ),
                            models.FieldCondition(
                                key="ordem", range=models.Range(gte=o - raio, lte=o + raio)
                            ),
                        ]
                    )
                    for doc, o in origem.values()
                ]
            )
            achados, _ = self.client.scroll(
                self.settings.collection_name,
                filtro,
                limit=len(origem) * 2 * raio + len(origem),
                with_payload=True,
            )
            por_chave = {
                ((a.payload or {}).get("document_id"), (a.payload or {}).get("ordem")): a
                for a in achados
            }
            saida: dict = {}
            for pid, (doc, o) in origem.items():
                vizinhos = {}
                for delta in range(-raio, raio + 1):
                    achado = por_chave.get((doc, o + delta))
                    if delta and achado:
                        fonte = self._fontes(
                            [
                                models.ScoredPoint(
                                    id=achado.id, version=0, score=0.0, payload=achado.payload
                                )
                            ]
                        )
                        if fonte:
                            vizinhos[delta] = fonte[0]
                saida[pid] = vizinhos
        return saida

    def close(self) -> None:
        self.client.close()
