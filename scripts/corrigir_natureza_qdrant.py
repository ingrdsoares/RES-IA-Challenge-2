"""Corrige a natureza de leis gravadas como "nao_informada" numa coleção Qdrant já carregada.

Aplica a mesma regra da carga (`natureza_do_documento` em src/rag/csv_para_qdrant.py) só ao
payload: não reembeda nem muda ids. Sem --aplicar, apenas lista o que mudaria.

Uso:
  python scripts/corrigir_natureza_qdrant.py --colecao knowledge_base_v2
  python scripts/corrigir_natureza_qdrant.py --colecao knowledge_base_v2 --aplicar
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http import models as qm  # noqa: E402

from src.rag.csv_para_qdrant import natureza_do_documento  # noqa: E402


def documentos_a_corrigir(client: QdrantClient, colecao: str) -> dict[str, dict]:
    """document_id -> {titulo, natureza nova, pontos} dos documentos que mudam."""
    filtro = qm.Filter(
        must=[qm.FieldCondition(key="natureza", match=qm.MatchValue(value="nao_informada"))]
    )
    docs: dict[str, dict] = defaultdict(lambda: {"pontos": 0})
    offset = None
    while True:
        pontos, offset = client.scroll(
            colecao,
            scroll_filter=filtro,
            limit=1000,
            offset=offset,
            with_payload=["document_id", "title", "natureza"],
            with_vectors=False,
        )
        for p in pontos:
            pl = p.payload or {}
            nova = natureza_do_documento(pl.get("title"), pl.get("natureza"))
            if nova != pl.get("natureza"):
                d = docs[pl["document_id"]]
                d["titulo"], d["natureza"] = pl.get("title"), nova
                d["pontos"] += 1
        if offset is None:
            return dict(docs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--colecao", required=True)
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--aplicar", action="store_true", help="grava; sem ela é só simulação")
    args = ap.parse_args(argv)

    client = QdrantClient(url=args.qdrant_url, timeout=120)
    docs = documentos_a_corrigir(client, args.colecao)
    for doc_id, d in sorted(docs.items(), key=lambda x: x[1]["titulo"] or ""):
        print(f"{d['pontos']:5d} pontos  {d['natureza']:<12} {d['titulo']}")
    print(f"{len(docs)} documento(s), {sum(d['pontos'] for d in docs.values())} ponto(s).")
    if not args.aplicar:
        print("Simulação: nada gravado. Use --aplicar para gravar.")
        return 0
    for doc_id, d in docs.items():
        client.set_payload(
            args.colecao,
            payload={"natureza": d["natureza"]},
            points=qm.Filter(
                must=[
                    qm.FieldCondition(key="document_id", match=qm.MatchValue(value=doc_id)),
                    qm.FieldCondition(key="natureza", match=qm.MatchValue(value="nao_informada")),
                ]
            ),
            wait=True,
        )
    print("Gravado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
