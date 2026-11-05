"""
Módulo RAG do Sócio Digital: Ingestão, Chunking Hierárquico, Recuperação Vetorial,
Extração de Entidades Fiscais e RAGService.
Frente de Ciência de Dados (Jhessica).
"""

from .chunker import LegalChunk, LegalHierarchicalChunker
from .entity_extractor import FiscalExtractionResult, TaxEntity, TaxEntityExtractor
from .evaluator import BenchmarkSummary, EvaluationResult, RAGEvaluator
from .ingest import IngestionPipeline
from .service import RAGService, RespostaCopiloto
from .vector_store import LegalVectorStore

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
    "RAGEvaluator",
    "BenchmarkSummary",
    "EvaluationResult",
]
