"""Serviço de embeddings: recebe textos e devolve um vetor normalizado por texto.

Substitui o Ollama nos embeddings com o mesmo modelo (Qwen3-Embedding-0.6B). Os vetores
coincidem com os já gravados no Qdrant (cosseno médio 0,999 em 25/11/2026), então a base
não precisa ser reindexada. Quem chama aplica a instrução de consulta; documentos vão crus.
"""

from typing import Annotated

import torch
import torch.nn.functional as F
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModel, AutoTokenizer

NOME = "Qwen/Qwen3-Embedding-0.6B"
REVISAO = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
MAX_TOKENS = 8192
TAMANHO_LOTE = 8

GPU = torch.cuda.is_available()
MPS = not GPU and torch.backends.mps.is_available()
DISPOSITIVO = "cuda" if GPU else "mps" if MPS else "cpu"
# Padding à esquerda: o último token de cada linha é o token real usado no pooling.
tokenizador = AutoTokenizer.from_pretrained(NOME, revision=REVISAO, padding_side="left")
modelo = AutoModel.from_pretrained(NOME, revision=REVISAO).eval().to(DISPOSITIVO)

app = FastAPI()


class Pedido(BaseModel):
    texts: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=40000)]],
        Field(min_length=1, max_length=64),
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "modelo": NOME, "dispositivo": DISPOSITIVO}


@app.post("/embed")
def embed(pedido: Pedido) -> dict[str, list[list[float]]]:
    vetores: list[list[float]] = []
    with torch.no_grad():
        for inicio in range(0, len(pedido.texts), TAMANHO_LOTE):
            entrada = tokenizador(
                pedido.texts[inicio : inicio + TAMANHO_LOTE],
                padding=True,
                truncation=True,
                max_length=MAX_TOKENS,
                return_tensors="pt",
            ).to(DISPOSITIVO)
            ultimo = modelo(**entrada).last_hidden_state[:, -1]
            vetores += F.normalize(ultimo, p=2, dim=1).float().tolist()
    return {"embeddings": vetores}
