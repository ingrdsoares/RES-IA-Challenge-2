"""
Módulo RAG do Sócio Digital: Ingestão, Chunking Hierárquico, Recuperação Vetorial,
Extração de Entidades Fiscais e RAGService.
Frente de Ciência de Dados (Jhessica).
"""

from .chunker import LegalHierarchicalChunker, LegalChunk
from .vector_store import LegalVectorStore
from .ingest import IngestionPipeline
from .entity_extractor import TaxEntityExtractor, TaxEntity, FiscalExtractionResult
from .service import RAGService, RespostaCopiloto

__all__ = [
    "LegalHierarchicalChunker",
    "LegalChunk",
    "LegalVectorStore",
    "IngestionPipeline",
    "TaxEntityExtractor",
    "TaxEntity",
    "FiscalExtractionResult",
    "RAGService",
    "RespostaCopiloto",
]
