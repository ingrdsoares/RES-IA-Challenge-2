import logging

import httpx

from app.config import Settings
from app.schemas import Source

logger = logging.getLogger(__name__)


class Reranker:
    """Cliente do serviço de reordenação; qualquer falha mantém a ordem da busca."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.url = str(settings.reranker_url) if settings.reranker_url else None
        self.client = client or httpx.Client(timeout=settings.reranker_timeout)

    def reordenar(self, pergunta: str, fontes: list[Source]) -> list[Source]:
        if not self.url or not fontes:
            return fontes
        try:
            resposta = self.client.post(
                self.url.rstrip("/") + "/rerank",
                json={"question": pergunta, "texts": [f.text for f in fontes]},
            )
            resposta.raise_for_status()
            notas = [float(n) for n in resposta.json()["scores"]]
            if len(notas) != len(fontes):
                raise ValueError(f"{len(notas)} notas para {len(fontes)} fontes")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Reranker indisponível, mantendo a ordem da busca: %s", exc)
            return fontes
        return [f for _, f in sorted(zip(notas, fontes, strict=True), key=lambda p: -p[0])]

    def close(self) -> None:
        self.client.close()
