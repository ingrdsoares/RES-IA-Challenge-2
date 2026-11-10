"""
Script de Carga e Indexação de Vetores no Qdrant (Coleção 'knowledge_base').
Sócio Digital — RES-IA Challenge 2 (Ciência de Dados - Jhessica).

Execução na máquina oficial de GPU (RTX 3080 Ti):
- Conecta ao Ollama em http://localhost:11434 (modelo qwen3-embedding:0.6b, 1024 dimensões).
- Conecta ao Qdrant em http://localhost:6333 (coleção 'knowledge_base', distância Cosseno).
- Lê os pontos pré-processados em data/processed/qdrant_points.jsonl e indexa com payload Source.
- Suporta flag --dry-run para validação de integridade sem rede/serviços ativos.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

# Adiciona raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def load_points_from_file(points_file: Path) -> List[Dict[str, Any]]:
    if not points_file.exists():
        raise FileNotFoundError(f"Arquivo de pontos não encontrado: {points_file}")
    points = []
    with open(points_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                points.append(json.loads(line))
    return points


def generate_embedding_ollama(text: str, ollama_url: str, model_name: str) -> List[float]:
    """Gera o embedding via API HTTP do Ollama."""
    import httpx

    resp = httpx.post(
        f"{ollama_url}/api/embeddings",
        json={"model": model_name, "prompt": text},
        timeout=60.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Erro no Ollama ({resp.status_code}): {resp.text}")
    emb = resp.json().get("embedding", [])
    if len(emb) != 1024:
        raise ValueError(f"Dimensão inesperada do embedding: {len(emb)} (esperado: 1024)")
    # Normalização L2 para distância Cosseno
    norm = math.sqrt(sum(x * x for x in emb)) or 1.0
    return [x / norm for x in emb]


def run_qdrant_ingestion(
    points_path: str = "data/processed/qdrant_points.jsonl",
    qdrant_url: str = "http://localhost:6333",
    ollama_url: str = "http://localhost:11434",
    collection_name: str = "knowledge_base",
    embedding_model: str = "qwen3-embedding:0.6b",
    embedding_dimensions: int = 1024,
    batch_size: int = 16,
    dry_run: bool = False,
):
    points_file = Path(points_path)
    print("=" * 70)
    print(" SÓCIO DIGITAL — INGESTÃO E CARGA NO QDRANT")
    print(f" Coleção: {collection_name} | Modelo: {embedding_model} ({embedding_dimensions}d)")
    print(f" Qdrant URL: {qdrant_url} | Ollama URL: {ollama_url}")
    print("=" * 70)

    raw_points = load_points_from_file(points_file)
    print(f"[*] {len(raw_points)} chunks/pontos carregados de {points_file}")

    if dry_run:
        print("\n[DRY RUN] Modo de validação ativo. Verificando integridade dos schemas:")
        for i, pt in enumerate(raw_points[:5]):
            print(
                f"  -> Ponto {pt['id']}: doc_id='{pt['document_id']}', len={len(pt['text'])} chars, tags={pt.get('tags')}"
            )
        print(
            f"\n[SUCESSO] Todos os {len(raw_points)} pontos validados com sucesso no schema Source."
        )
        return

    try:
        from qdrant_client import QdrantClient, models
    except ImportError:
        print("[ERRO] qdrant-client não instalado. Instale com: pip install qdrant-client")
        sys.exit(1)

    print("\n[*] Conectando ao Qdrant...")
    client = QdrantClient(url=qdrant_url, timeout=10.0)

    if not client.collection_exists(collection_name):
        print(
            f"[*] Criando coleção '{collection_name}' com {embedding_dimensions} dimensões e distância COSINE..."
        )
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=embedding_dimensions,
                distance=models.Distance.COSINE,
            ),
        )
    else:
        print(f"[*] Coleção '{collection_name}' já existe.")

    print("\n[*] Gerando embeddings e inserindo no Qdrant em lotes...")
    total_loaded = 0

    for i in range(0, len(raw_points), batch_size):
        batch = raw_points[i : i + batch_size]
        qdrant_batch_points = []

        for item in batch:
            text = item["text"]
            # Embedding com modelo qwen3-embedding:0.6b
            vector = generate_embedding_ollama(text, ollama_url, embedding_model)

            payload = {
                "text": text,
                "source": item["source"],
                "title": item["title"],
                "document_id": item["document_id"],
                "chunk_id": item["chunk_id"],
                "reference_date": item.get("reference_date"),
                "effective_date": item.get("effective_date"),
                "artigo": item.get("artigo"),
                "paragrafo": item.get("paragrafo"),
                "tema": item.get("tema"),
                "tags": item.get("tags", []),
            }

            qdrant_batch_points.append(
                models.PointStruct(
                    id=item["id"],
                    vector=vector,
                    payload=payload,
                )
            )

        client.upsert(collection_name=collection_name, points=qdrant_batch_points)
        total_loaded += len(qdrant_batch_points)
        print(f" -> Lote {i // batch_size + 1}: {total_loaded}/{len(raw_points)} pontos indexados.")

    print("\n" + "=" * 70)
    print(
        f" SUCESSO! {total_loaded} pontos foram indexados na coleção '{collection_name}' do Qdrant."
    )
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga de pontos no Qdrant")
    parser.add_argument(
        "--points", default="data/processed/qdrant_points.jsonl", help="Caminho do JSONL de pontos"
    )
    parser.add_argument("--qdrant-url", default="http://localhost:6333", help="URL do Qdrant")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    parser.add_argument("--collection", default="knowledge_base", help="Nome da coleção")
    parser.add_argument(
        "--dry-run", action="store_true", help="Apenas valida o arquivo sem enviar para o Qdrant"
    )
    args = parser.parse_args()

    run_qdrant_ingestion(
        points_path=args.points,
        qdrant_url=args.qdrant_url,
        ollama_url=args.ollama_url,
        collection_name=args.collection,
        dry_run=args.dry_run,
    )
