"""
Modelos de dados estruturados para o Motor Fiscal do Sócio Digital.
Responsável: Engenharia de Dados & Dev (Lucas)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CNAEItem:
    codigo: str
    codigo_limpo: str
    descricao: str
    setor: str
    anexo_padrao: str  # I, II, III, IV, V
    sujeito_fator_r: bool
    permitido_simples: bool
    permitido_mei: bool
    ocupacao_mei: Optional[str] = None
    tributos: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "CNAEItem":
        codigo = data["codigo"]
        codigo_limpo = "".join(filter(str.isdigit, codigo))
        return cls(
            codigo=codigo,
            codigo_limpo=codigo_limpo,
            descricao=data["descricao"],
            setor=data.get("setor", "Outros"),
            anexo_padrao=data["anexo_padrao"],
            sujeito_fator_r=data.get("sujeito_fator_r", False),
            permitido_simples=data.get("permitido_simples", True),
            permitido_mei=data.get("permitido_mei", False),
            ocupacao_mei=data.get("ocupacao_mei"),
            tributos=data.get("tributos", []),
        )


@dataclass
class FaixaSimples:
    faixa: int
    de: float
    ate: float
    aliquota_nominal: float
    parcela_deduzir: float
    reparticao: Dict[str, float] = field(default_factory=dict)


@dataclass
class CalculoSimplesResultado:
    rbt12: float
    faturamento_mes: float
    anexo_aplicado: str
    faixa: int
    aliquota_nominal: float
    parcela_deduzir: float
    aliquota_efetiva: float  # Ex: 0.0845 = 8.45%
    imposto_mes: float
    decomposicao_tributos: Dict[str, float]
    fator_r_percentual: Optional[float] = None
    migrou_anexo_por_fator_r: bool = False


@dataclass
class SimulacaoComparativaResultado:
    cnae: CNAEItem
    faturamento_anual: float
    faturamento_mensal: float
    folha_12m: float
    fator_r: float
    mei_elegivel: bool
    mei_motivo_inelegibilidade: Optional[str]
    mei_custo_mensal: Optional[float]
    simples_resultado: CalculoSimplesResultado
    recomendacao_regime: str
    economia_mensal_mei: Optional[float]
    alertas: List[str] = field(default_factory=list)

