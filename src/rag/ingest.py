"""
Pipeline de Ingestão e Processamento de Documentos Legais Fiscais.
Sócio Digital — RES-IA Challenge 2 (Ciência de Dados - Jhessica).
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .chunker import LegalHierarchicalChunker, LegalChunk
from .vector_store import LegalVectorStore


class IngestionPipeline:
    """
    Controlador do pipeline de ingestão:
    1. Leitura de fontes primárias em `data/raw`
    2. Segmentação hierárquica por Artigos/Parágrafos
    3. Indexação e vetorização
    4. Geração de manifesto de governança
    """

    def __init__(
        self,
        raw_dir: str = "data/raw",
        db_path: str = "data/processed/vector_index.db",
        manifest_path: str = "data/processed/manifest.json",
        max_chunk_chars: int = 1200,
        use_dense: bool = True,
    ):
        self.raw_dir = Path(raw_dir)
        self.db_path = Path(db_path)
        self.manifest_path = Path(manifest_path)
        self.chunker = LegalHierarchicalChunker(max_chunk_chars=max_chunk_chars)
        self.vector_store = LegalVectorStore(db_path=str(self.db_path), use_dense=use_dense)

    def run(self) -> Dict[str, Any]:
        """Executa a ingestão completa de todos os documentos presentes em data/raw."""
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Diretório de dados brutos não encontrado: {self.raw_dir}")

        files = list(self.raw_dir.glob("*.md")) + list(self.raw_dir.glob("*.txt"))
        if not files:
            print(f"[IngestionPipeline] Nenhum arquivo encontrado em {self.raw_dir}.")
            return {}

        print(f"[IngestionPipeline] Iniciando ingestão de {len(files)} documentos fiscais...")

        all_chunks: List[LegalChunk] = []
        doc_summaries: List[Dict[str, Any]] = []

        for fpath in files:
            doc_name = fpath.stem.replace("_", " ").title()
            # Mapeamento para nomes formais
            if "lc_123" in fpath.name.lower():
                doc_name = "Lei Complementar nº 123/2006 (Estatuto da MPE)"
            elif "resolucao_cgsn" in fpath.name.lower():
                doc_name = "Resolução CGSN nº 140/2018 (Regulamento Simples Nacional)"
            elif "manual_regularizacao" in fpath.name.lower():
                doc_name = "Manual de Regularização Fiscal e CND (Receita Federal)"

            with open(fpath, "r", encoding="utf-8") as f:
                raw_text = f.read()

            chunks = self.chunker.chunk_document(raw_text, source_doc=doc_name)
            all_chunks.extend(chunks)

            doc_summaries.append({
                "file": fpath.name,
                "source_doc": doc_name,
                "size_bytes": len(raw_text.encode("utf-8")),
                "total_chunks": len(chunks),
                "articles": sorted(list(set(c.artigo for c in chunks))),
            })
            print(f" -> {fpath.name}: {len(chunks)} chunks gerados.")

        # Armazena e indexa vetores
        self.vector_store.add_chunks(all_chunks)

        # Estatísticas finais
        stats = self.vector_store.get_stats()

        manifest = {
            "pipeline_version": "1.0.0",
            "frente": "Ciência de Dados (Jhessica)",
            "projeto": "Sócio Digital",
            "stats": stats,
            "documents": doc_summaries,
            "total_chunks_indexed": len(all_chunks),
        }

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"[IngestionPipeline] Ingestão concluída com sucesso! Manifesto gerado em: {self.manifest_path}")
        return manifest


if __name__ == "__main__":
    pipeline = IngestionPipeline()
    pipeline.run()
