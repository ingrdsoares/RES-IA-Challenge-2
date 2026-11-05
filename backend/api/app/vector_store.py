import logging

from pydantic import ValidationError
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import Settings
from app.errors import CollectionIncompatible, dependency_errors
from app.schemas import Source

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, settings: Settings, client: QdrantClient | None = None):
        self.settings = settings
        self.client = client if client is not None else QdrantClient(
            url=str(settings.qdrant_url), timeout=settings.qdrant_timeout,
        )

    def ensure_collection(self) -> None:
        with dependency_errors("Qdrant"):
            if not self.client.collection_exists(self.settings.collection_name):
                try:
                    self.client.create_collection(
                        collection_name=self.settings.collection_name,
                        vectors_config=models.VectorParams(
                            size=self.settings.embedding_dimensions, distance=models.Distance.COSINE,
                        ),
                    )
                except UnexpectedResponse as exc:
                    if exc.status_code != 409:
                        raise
            vectors = self.client.get_collection(self.settings.collection_name).config.params.vectors
            if (not isinstance(vectors, models.VectorParams)
                    or vectors.size != self.settings.embedding_dimensions
                    or vectors.distance != models.Distance.COSINE):
                raise CollectionIncompatible("A coleção vetorial tem configuração incompatível.")

    def count(self) -> int:
        with dependency_errors("Qdrant"):
            return self.client.count(self.settings.collection_name, exact=True).count

    def search(self, vector: list[float]) -> list[Source]:
        with dependency_errors("Qdrant"):
            hits = self.client.query_points(
                collection_name=self.settings.collection_name, query=vector,
                limit=self.settings.top_k, score_threshold=self.settings.score_threshold,
                with_payload=True,
            ).points
        sources = []
        for hit in hits:
            try:
                sources.append(Source.model_validate(
                    (hit.payload or {}) | {"id": hit.id, "score": hit.score},
                ))
            except ValidationError:
                logger.warning("Trecho %s descartado: payload inválido", hit.id)
        return sources

    def close(self) -> None:
        self.client.close()
