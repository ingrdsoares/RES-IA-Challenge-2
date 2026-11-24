"""
Módulo de processamento multimodal de documentos fiscais.
Sócio Digital — RES-IA Challenge 2 (Grupo 08).
"""

from app.assistant.multimodal.pdf_parser import MultimodalPDFParser, parse_currency
from app.assistant.multimodal.schemas import MultimodalDocumentResult

__all__ = [
    "MultimodalPDFParser",
    "MultimodalDocumentResult",
    "parse_currency",
]
