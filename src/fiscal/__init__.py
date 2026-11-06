"""
Módulo Fiscal — Sócio Digital (RES-IA Challenge 2).
Responsável: Engenharia de Dados & Dev (Lucas).
"""

from src.fiscal.calculator import FiscalCalculator
from src.fiscal.ingest import FiscalIngestionPipeline
from src.fiscal.models import (
    CalculoSimplesResultado,
    CNAEItem,
    FaixaSimples,
    SimulacaoComparativaResultado,
)
from src.fiscal.repository import FiscalRepository

__all__ = [
    "CNAEItem",
    "FaixaSimples",
    "CalculoSimplesResultado",
    "SimulacaoComparativaResultado",
    "FiscalIngestionPipeline",
    "FiscalRepository",
    "FiscalCalculator",
]
