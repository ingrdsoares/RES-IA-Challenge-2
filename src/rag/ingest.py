"""
Pipeline de Ingestão e Processamento de Documentos Legais Fiscais.
Sócio Digital — RES-IA Challenge 2 (Ciência de Dados - Jhessica).

Alinhamento Arquitetural (Plano de Entrega de 09/11/2026):
1. Ingestão do acervo refinado e documentos centrais da demonstração.
2. Chunking Hierárquico Jurídico: até 2.000 caracteres, overlap de 200 caracteres.
3. Compatibilidade direta com Qdrant (1024 dimensões, distância Cosseno) e SQLite de desenvolvimento.
4. Exportação estruturada dos pontos para carga no Qdrant (app.schemas.Source).
5. Geração de manifesto com hashes SHA-256 e auditoria completa.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chunker import LegalChunk, LegalHierarchicalChunker
from .vector_store import LegalVectorStore


def parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    """Extrai metadados de frontmatter YAML/Markdown caso existam no topo do arquivo."""
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text

    parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
    if len(parts) < 3:
        return {}, text

    meta: Dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip().strip("\"'")

    body = parts[2].strip()
    return meta, body


class IngestionPipeline:
    """
    Controlador do pipeline de ingestão:
    1. Leitura de fontes primárias em `data/raw` e acervo refinado
    2. Segmentação hierárquica por Artigos/Parágrafos (até 2000 chars, overlap 200)
    3. Indexação e vetorização (1024 dimensões)
    4. Exportação dos pontos formatados para carga no Qdrant
    5. Geração de manifesto de governança MLOps
    """

    def __init__(
        self,
        raw_dir: str = "data/raw",
        db_path: str = "data/processed/vector_index.db",
        manifest_path: str = "data/processed/manifest.json",
        qdrant_points_path: str = "data/processed/qdrant_points.jsonl",
        max_chunk_chars: int = 2000,
        overlap_chars: int = 200,
        use_dense: bool = True,
    ):
        self.raw_dir = Path(raw_dir)
        self.db_path = Path(db_path)
        self.manifest_path = Path(manifest_path)
        self.qdrant_points_path = Path(qdrant_points_path)
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars
        self.chunker = LegalHierarchicalChunker(
            max_chunk_chars=max_chunk_chars,
            overlap_chars=overlap_chars,
        )
        self.vector_store = LegalVectorStore(
            db_path=str(self.db_path),
            use_dense=use_dense,
        )

    def _resolve_document_metadata(
        self, fpath: Path, raw_text: str
    ) -> tuple[str, str, Optional[str], Optional[str], str]:
        """Extrai metadados canônicos do documento: (document_id, doc_name, ref_date, eff_date, body)."""
        front_meta, body = parse_frontmatter(raw_text)

        fname = fpath.stem.lower()
        doc_id = front_meta.get("document_id") or front_meta.get("id") or fname
        doc_name = front_meta.get("title") or front_meta.get("titulo")

        ref_date = front_meta.get("reference_date") or front_meta.get("coletado_em")
        eff_date = front_meta.get("effective_date") or front_meta.get("data_publicacao")

        # Mapeamento para nomes formais conhecidos
        if not doc_name:
            if "lc_123" in fname or "lc123" in fname:
                doc_name = "Lei Complementar nº 123/2006 (Estatuto da MPE)"
                doc_id = "lc123"
            elif "cgsn_140" in fname or "cgsn140" in fname:
                doc_name = "Resolução CGSN nº 140/2018 (Regulamento Simples Nacional)"
                doc_id = "cgsn140"
            elif "manual_regularizacao" in fname:
                doc_name = "Manual de Regularização Fiscal e CND (Receita Federal)"
                doc_id = "manual_regularizacao"
            elif "ctn" in fname:
                doc_name = "Lei nº 5.172/1966 — Código Tributário Nacional (CTN)"
                doc_id = "ctn"
            elif "lc116" in fname or "lc_116" in fname:
                doc_name = "Lei Complementar nº 116/2003 (ISSQN e Lista de Serviços)"
                doc_id = "lc116"
            elif "lgpd" in fname:
                doc_name = "Lei nº 13.709/2018 (Lei Geral de Proteção de Dados - LGPD)"
                doc_id = "lgpd"
            elif "ec132" in fname:
                doc_name = "Emenda Constitucional nº 132/2023 (Reforma Tributária do Consumo)"
                doc_id = "ec132"
            elif "decreto25508" in fname or "decreto_25508" in fname:
                doc_name = "Decreto Distrital nº 25.508/2005 (RISS-DF - Regulamento do ISS)"
                doc_id = "decreto25508"
            elif "decreto43982" in fname or "decreto_43982" in fname:
                doc_name = "Decreto Distrital nº 43.982/2022 (RICMS-DF - Regulamento do ICMS)"
                doc_id = "decreto43982"
            else:
                doc_name = fpath.stem.replace("_", " ").title()

        # Validação do formato de data ISO YYYY-MM-DD
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        if ref_date and not iso_pattern.match(ref_date):
            ref_date = None
        if eff_date and not iso_pattern.match(eff_date):
            eff_date = None

        return doc_id, doc_name, ref_date, eff_date, body

    def run(self) -> Dict[str, Any]:
        """Executa a ingestão completa de todos os documentos presentes em data/raw."""
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Diretório de dados brutos não encontrado: {self.raw_dir}")

        files = sorted(
            list(self.raw_dir.glob("*.md"))
            + list(self.raw_dir.glob("*.txt"))
            + list(self.raw_dir.glob("*/*.md"))
        )
        if not files:
            print(f"[IngestionPipeline] Nenhum arquivo encontrado em {self.raw_dir}.")
            return {}

        print(
            f"[IngestionPipeline] Iniciando ingestão hierárquica de {len(files)} documentos fiscais..."
        )

        all_chunks: List[LegalChunk] = []
        doc_summaries: List[Dict[str, Any]] = []

        for fpath in files:
            with open(fpath, "r", encoding="utf-8") as f:
                raw_text = f.read()

            file_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            doc_id, doc_name, ref_date, eff_date, body = self._resolve_document_metadata(
                fpath, raw_text
            )

            chunks = self.chunker.chunk_document(
                text=body,
                source_doc=doc_name,
                document_id=doc_id,
                title=doc_name,
                reference_date=ref_date,
                effective_date=eff_date,
            )
            all_chunks.extend(chunks)

            doc_summaries.append(
                {
                    "file": str(fpath.relative_to(self.raw_dir)),
                    "document_id": doc_id,
                    "source_doc": doc_name,
                    "sha256": file_hash,
                    "size_bytes": len(raw_text.encode("utf-8")),
                    "total_chunks": len(chunks),
                    "reference_date": ref_date,
                    "effective_date": eff_date,
                    "articles": sorted(list(set(c.artigo for c in chunks if c.artigo))),
                }
            )
            print(f" -> {fpath.name} (id: {doc_id}): {len(chunks)} chunks gerados.")

        # Armazena e indexa vetores no banco local (SQLite com fallback/Ollama)
        self.vector_store.add_chunks(all_chunks)

        # Exporta pontos preparados para carga direta no Qdrant
        self.qdrant_points_path.parent.mkdir(parents=True, exist_ok=True)
        qdrant_points_count = 0
        with open(self.qdrant_points_path, "w", encoding="utf-8") as f_qdrant:
            for idx, chunk in enumerate(all_chunks, 1):
                # Formato compatível com o schema Source do backend/api
                point = {
                    "id": idx,
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source_doc,
                    "title": chunk.title or chunk.source_doc,
                    "text": chunk.content,
                    "reference_date": chunk.reference_date,
                    "effective_date": chunk.effective_date,
                    "artigo": chunk.artigo,
                    "paragrafo": chunk.paragrafo,
                    "tema": chunk.tema,
                    "tags": chunk.metadata.get("tags", []),
                }
                f_qdrant.write(json.dumps(point, ensure_ascii=False) + "\n")
                qdrant_points_count += 1

        stats = self.vector_store.get_stats()

        manifest = {
            "pipeline_version": "2.0.0",
            "frente": "Ciência de Dados (Jhessica)",
            "projeto": "Sócio Digital",
            "embedding_model": "qwen3-embedding:0.6b",
            "embedding_dimensions": 1024,
            "metric": "cosine",
            "chunking_strategy": {
                "type": "hierarquico_juridico",
                "max_chunk_chars": self.max_chunk_chars,
                "overlap_chars": self.overlap_chars,
                "context_injection": True,
            },
            "stats": stats,
            "qdrant_points_file": str(self.qdrant_points_path),
            "total_qdrant_points": qdrant_points_count,
            "documents": doc_summaries,
            "total_chunks_indexed": len(all_chunks),
        }

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"[IngestionPipeline] Ingestão concluída! Manifesto em: {self.manifest_path}")
        print(f"[IngestionPipeline] Pontos Qdrant exportados em: {self.qdrant_points_path}")
        return manifest


if __name__ == "__main__":
    pipeline = IngestionPipeline()
    pipeline.run()
