"""
Módulo RAG do Sócio Digital: Ingestão, Chunking Hierárquico, Recuperação Vetorial
e Extração de Entidades Fiscais.
Frente de Ciência de Dados (Jhessica).
"""

from .chunker import LegalHierarchicalChunker, LegalChunk
from .vector_store import LegalVectorStore
from .ingest import IngestionPipeline
from .entity_extractor import TaxEntityExtractor, TaxEntity, FiscalExtractionResult

__all__ = [
    "LegalHierarchicalChunker",
    "LegalChunk",
    "LegalVectorStore",
    "IngestionPipeline",
    "TaxEntityExtractor",
    "TaxEntity",
    "FiscalExtractionResult",
]
