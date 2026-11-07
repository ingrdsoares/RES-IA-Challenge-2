"""Serviço de reordenação: recebe pergunta e textos, devolve uma nota por texto."""

from typing import Annotated

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

NOME = "BAAI/bge-reranker-v2-m3"
REVISAO = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
MAX_TOKENS = 512
TAMANHO_LOTE = 8

GPU = torch.cuda.is_available()
DISPOSITIVO = "cuda" if GPU else "cpu"
tokenizador = AutoTokenizer.from_pretrained(NOME, revision=REVISAO)
modelo = AutoModelForSequenceClassification.from_pretrained(NOME, revision=REVISAO).eval()
if GPU:
    modelo = modelo.half()
modelo = modelo.to(DISPOSITIVO)

app = FastAPI()


class Pedido(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=2000)]
    texts: Annotated[list[str], Field(max_length=300)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "dispositivo": DISPOSITIVO}


@app.post("/rerank")
def rerank(pedido: Pedido) -> dict[str, list[float]]:
    notas: list[float] = []
    with torch.no_grad():
        for inicio in range(0, len(pedido.texts), TAMANHO_LOTE):
            lote = pedido.texts[inicio : inicio + TAMANHO_LOTE]
            entrada = tokenizador(
                [pedido.question] * len(lote),
                lote,
                padding=True,
                truncation=True,
                max_length=MAX_TOKENS,
                return_tensors="pt",
            ).to(DISPOSITIVO)
            notas += modelo(**entrada).logits.view(-1).tolist()
    if GPU:
        # Devolve a sobra ao Ollama, que divide a mesma VRAM.
        torch.cuda.empty_cache()
    return {"scores": notas}
