"""Ponte do recorte CSV (recorte_csv) para a coleção Qdrant que a API consulta.

Reusa a configuração, o cliente Ollama e o cliente/coleção da API (backend/api/app).
Documentos são embeddados sem o prefixo de instrução que a API põe na pergunta
(QUERY_INSTRUCTION em app/models.py): o prefixo é só do lado da consulta.

Uso:
  python -m src.rag.csv_para_qdrant --csv <arquivo.csv> [--limite N] [--dry-run]
"""

import argparse
import csv
import itertools
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

BACKEND_API = Path(__file__).resolve().parents[2] / "backend" / "api"
if str(BACKEND_API) not in sys.path:
    sys.path.insert(0, str(BACKEND_API))

from app.config import Settings  # noqa: E402
from app.errors import DependencyUnavailable, dependency_errors  # noqa: E402
from app.models import LocalModels  # noqa: E402
from app.vector_store import VectorStore  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client import models as qm  # noqa: E402

from src.rag.chunker import LegalChunk, LegalHierarchicalChunker  # noqa: E402

TAMANHO_LOTE = 64
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "socio-digital/recorte-rag-v1")
CHUNKER = LegalHierarchicalChunker()

Embed = Callable[[list[str]], list[list[float]]]


def ler_csv(caminho: Path) -> Iterator[dict]:
    csv.field_size_limit(2**31 - 1)
    with open(caminho, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def ponto_id(versao_id: str, indice: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{versao_id}:{indice}"))


def payload(linha: dict, chunk: LegalChunk) -> dict:
    return {
        "text": chunk.content,
        "source": linha["source_url"],
        "title": linha["titulo"] or None,
        "document_id": linha["documento_id"],
        "chunk_id": chunk.chunk_id,
    }


def _itens(linhas: Iterator[dict]) -> Iterator[tuple[str, str, dict]]:
    for linha in linhas:
        for indice, chunk in enumerate(CHUNKER.chunk_document(linha["texto"], linha["titulo"])):
            yield ponto_id(linha["versao_id"], indice), chunk.content, payload(linha, chunk)


def _gravar(client: QdrantClient, settings: Settings, embed: Embed, lote: list) -> None:
    vetores = embed([texto for _, texto, _ in lote])
    if len(vetores) != len(lote):
        raise DependencyUnavailable("Quantidade de embeddings diferente da de chunks.")
    client.upsert(
        collection_name=settings.collection_name,
        points=[
            qm.PointStruct(id=pid, vector=vetor, payload=dados)
            for (pid, _, dados), vetor in zip(lote, vetores, strict=True)
        ],
    )


def ingerir(
    caminho_csv: Path,
    *,
    settings: Settings,
    client: QdrantClient,
    embed: Embed,
    limite: int | None = None,
) -> int:
    VectorStore(settings, client).ensure_collection()
    total = 0
    lote: list = []
    for item in _itens(itertools.islice(ler_csv(caminho_csv), limite)):
        lote.append(item)
        if len(lote) == TAMANHO_LOTE:
            _gravar(client, settings, embed, lote)
            total += len(lote)
            lote = []
    if lote:
        _gravar(client, settings, embed, lote)
        total += len(lote)
    return total


def resumo_dry_run(caminho_csv: Path, *, settings: Settings, limite: int | None = None) -> dict:
    documentos = 0
    chunks = 0
    bytes_texto = 0
    for linha in itertools.islice(ler_csv(caminho_csv), limite):
        documentos += 1
        for chunk in CHUNKER.chunk_document(linha["texto"], linha["titulo"]):
            chunks += 1
            bytes_texto += len(chunk.content.encode("utf-8"))
    return {
        "documentos": documentos,
        "chunks": chunks,
        "bytes_texto_chunks": bytes_texto,
        "bytes_vetores_estimados": chunks * settings.embedding_dimensions * 4,
    }


def embedder_ollama(settings: Settings) -> Embed:
    models = LocalModels(settings)

    def embed(textos: list[str]) -> list[list[float]]:
        with dependency_errors("Ollama"):
            vetores = models.client.embed(
                model=settings.embedding_model, input=textos, truncate=False
            ).embeddings
        if len(vetores) != len(textos) or any(
            len(v) != settings.embedding_dimensions for v in vetores
        ):
            raise DependencyUnavailable("Embedding inválido retornado pelo Ollama.")
        return [list(v) for v in vetores]

    return embed


def main(
    argv: list[str] | None = None,
    *,
    embed: Embed | None = None,
    client: QdrantClient | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Sobe o recorte CSV para o Qdrant.")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings()

    if args.dry_run:
        r = resumo_dry_run(args.csv, settings=settings, limite=args.limite)
        print(f"documentos: {r['documentos']}")
        print(f"chunks: {r['chunks']}")
        print(f"bytes de texto dos chunks: {r['bytes_texto_chunks']}")
        print(
            f"bytes de vetores estimados ({settings.embedding_dimensions} float32): "
            f"{r['bytes_vetores_estimados']}"
        )
        return 0

    if client is None:
        client = QdrantClient(url=str(settings.qdrant_url), timeout=settings.qdrant_timeout)
    if embed is None:
        embed = embedder_ollama(settings)
    total = ingerir(args.csv, settings=settings, client=client, embed=embed, limite=args.limite)
    print(f"pontos gravados (upsert): {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
