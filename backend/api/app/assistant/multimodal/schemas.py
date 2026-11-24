"""
Contratos e schemas para extração multimodal de documentos fiscais.
Sócio Digital — RES-IA Challenge 2 (Grupo 08).
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Literal, Optional


@dataclass
class MultimodalDocumentResult:
    """Resultado da extração estruturada de um documento fiscal (ex.: DASN-SIMEI)."""

    document_type: Literal["DASN-SIMEI", "PGMEI", "UNKNOWN"] = "UNKNOWN"
    numero_recibo: Optional[str] = None
    ano_calendario: Optional[int] = None
    tipo_declaracao: Optional[str] = None
    cnpj: Optional[str] = None
    razao_social: Optional[str] = None
    cnae_principal: Optional[str] = None
    possui_empregado: Optional[bool] = None

    # Valores monetários (em reais)
    receita_comercio: float = 0.0
    receita_servicos: float = 0.0
    receita_total: float = 0.0
    limite_anual: float = 81000.0

    # Diagnóstico fiscal
    excesso_valor: float = 0.0
    excesso_percentual: float = 0.0
    faixa_excesso: Literal["dentro_do_limite", "ate_20_porcento", "acima_20_porcento"] = (
        "dentro_do_limite"
    )
    efeito_enquadramento: str = "manutencao_simei"
    data_efeito: Optional[str] = None
    fundamentacao_legal: str = "Art. 18-A da LC 123/2006"

    # Metadados de extração
    texto_bruto: str = ""
    confianca: float = 1.0
    metadados_adicionais: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        return asdict(self)

    def to_prompt_context(self) -> str:
        """Gera um bloco de contexto textual estruturado para injeção no prompt dos agentes."""
        lines = [
            "=== DADOS EXTRAÍDOS DO DOCUMENTO FISCAL (DASN-SIMEI) ===",
            f"Tipo de Documento: {self.document_type}",
            f"CNPJ: {self.cnpj or 'Não identificado'}",
            f"Razão Social: {self.razao_social or 'Não identificada'}",
            f"Ano-Calendário: {self.ano_calendario or 'Não informado'}",
            f"Receita Bruta Comércio/Indústria: R$ {self.receita_comercio:,.2f}",
            f"Receita Bruta Serviços: R$ {self.receita_servicos:,.2f}",
            f"Receita Bruta Total Declarada: R$ {self.receita_total:,.2f}",
            f"Limite Anual do MEI: R$ {self.limite_anual:,.2f}",
            f"Excesso Apurado: R$ {self.excesso_valor:,.2f} ({self.excesso_percentual:.2f}%)",
            f"Diagnóstico Fiscal: {self.faixa_excesso.upper()}",
            f"Efeito Legal: {self.efeito_enquadramento}",
            f"Base Legal: {self.fundamentacao_legal}",
            "=======================================================",
        ]
        return "\n".join(lines)
