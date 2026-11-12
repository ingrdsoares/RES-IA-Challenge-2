import logging
import math

import httpx

from app.config import Settings
from app.schemas import Source

logger = logging.getLogger(__name__)
# Limite de textos por pedido do serviço (backend/reranker/main.py).
MAX_TEXTOS = 300


def _sigmoide(x: float) -> float:
    return 1 / (1 + math.exp(-max(min(x, 500.0), -500.0)))


class Reranker:
    """Cliente do serviço de reordenação; qualquer falha mantém a ordem da busca."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.url = str(settings.reranker_url) if settings.reranker_url else None
        if not self.url:
            logger.warning(
                "RERANKER_URL não definida: a busca segue só com a ordem híbrida (recall reduzido)"
            )
        self.legislacao_boost = settings.rerank_legislation_boost
        self.client = client or httpx.Client(timeout=settings.reranker_timeout)

    def reordenar(self, pergunta: str, fontes: list[Source]) -> list[Source]:
        if not self.url or not fontes:
            return fontes
        # O serviço recusa mais de MAX_TEXTOS; o excedente segue na ordem da busca, depois.
        fontes, resto = fontes[:MAX_TEXTOS], fontes[MAX_TEXTOS:]
        return self._reordenar(pergunta, fontes) + resto

    def _reordenar(self, pergunta: str, fontes: list[Source]) -> list[Source]:
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
        if self.legislacao_boost > 0:
            # O serviço devolve logits (sem limite). A sigmoide leva a nota para 0..1, e o
            # bônus passa a significar "pontos de probabilidade de relevância" (estável
            # entre modelos). Com bônus 0 usa-se o logit cru, preservando a ordem atual.
            notas = [
                _sigmoide(n) + (self.legislacao_boost if f.natureza == "legislacao" else 0.0)
                for n, f in zip(notas, fontes, strict=True)
            ]
        return [f for _, f in sorted(zip(notas, fontes, strict=True), key=lambda p: -p[0])]

    def close(self) -> None:
        self.client.close()
