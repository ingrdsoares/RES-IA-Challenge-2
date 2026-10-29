"""
Módulo RAG do Sócio Digital: Ingestão, Chunking Hierárquico e Recuperação Vetorial.
Frente de Ciência de Dados (Jhessica).
"""

from .chunker import LegalHierarchicalChunker, LegalChunk
from .vector_store import LegalVectorStore
from .ingest import IngestionPipeline

__all__ = [
    "LegalHierarchicalChunker",
    "LegalChunk",
    "LegalVectorStore",
    "IngestionPipeline",
]
