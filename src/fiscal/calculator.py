"""
Motor Determinístico de Regras Fiscais (Simples Nacional, MEI e Fator R).
Sócio Digital — RES-IA Challenge 2 (Lucas).

Arquitetura: Clara e Nasser
Diretriz: Cálculos matemáticos são 100% determinísticos e auditáveis.
"""

from typing import Optional

from src.fiscal.models import (
    CalculoSimplesResultado,
    CNAEItem,
    SimulacaoComparativaResultado,
)
from src.fiscal.repository import FiscalRepository


class FiscalCalculator:
    def __init__(self, repository: FiscalRepository):
        self.repo = repository

        # Parâmetros
        self.limite_simples = float(self.repo.get_parametro("limite_anual_simples") or 4800000.0)
        self.limite_mei = float(self.repo.get_parametro("limite_anual_mei") or 81000.0)
        self.tolerancia_mei = float(self.repo.get_parametro("tolerancia_limite_mei") or 0.20)
        self.salario_minimo = float(self.repo.get_parametro("salario_minimo_referencia") or 1412.0)
        self.mei_inss_perc = float(self.repo.get_parametro("mei_inss_percentual") or 0.05)
        self.mei_icms_fixo = float(self.repo.get_parametro("mei_icms_fixo") or 1.0)
        self.mei_iss_fixo = float(self.repo.get_parametro("mei_iss_fixo") or 5.0)

    def calcular_fator_r(self, folha_12m: float, rbt12: float) -> float:
        """
        Calcula o Fator R (Folha de Salários últimos 12m / Receita Bruta últimos 12m).
        Art. 18, §§ 5º-J e 5º-M da LC 123/2006.
        """
        if rbt12 <= 0:
            return 0.0
        return round(folha_12m / rbt12, 4)

    def determinar_anexo(self, cnae: CNAEItem, fator_r: float) -> tuple[str, bool]:
        """
        Determina o Anexo aplicável.
        Se o CNAE estiver no rol do Fator R:
        - Fator R >= 0.28 (28%) -> Anexo III
        - Fator R < 0.28 -> Anexo V
        """
        if cnae.sujeito_fator_r:
            if fator_r >= 0.28:
                return "III", True
            else:
                return "V", False
        return cnae.anexo_padrao, False

    def calcular_aliquota_efetiva(
        self,
        rbt12: float,
        anexo: str,
        faturamento_mes: Optional[float] = None,
        fator_r_percentual: Optional[float] = None,
        migrou_fator_r: bool = False,
    ) -> CalculoSimplesResultado:
        """
        Calcula a alíquota efetiva oficial do Simples Nacional pela fórmula:
        Alíquota Efetiva = ((RBT12 * Alíquota Nominal) - Parcela a Deduzir) / RBT12
        """
        if faturamento_mes is None:
            faturamento_mes = rbt12 / 12.0 if rbt12 > 0 else 0.0

        faixa = self.repo.get_faixa_adequada(anexo, rbt12)
        if not faixa:
            raise ValueError(f"Não foi possível localizar faixa para Anexo {anexo} e RBT12 {rbt12}")

        # Se faturamento acumulado for zero ou na 1ª faixa, alíquota efetiva é a nominal
        if rbt12 <= 0 or faixa.faixa == 1:
            aliquota_efetiva = faixa.aliquota_nominal
        else:
            aliquota_efetiva = ((rbt12 * faixa.aliquota_nominal) - faixa.parcela_deduzir) / rbt12

        # Arredonda alíquota efetiva para 4 casas decimais
        aliquota_efetiva = max(round(aliquota_efetiva, 4), 0.0)
        imposto_mes = round(faturamento_mes * aliquota_efetiva, 2)

        # Decomposição de tributos por imposto
        decomposicao = {}
        for trib, share in faixa.reparticao.items():
            valor_trib = round(imposto_mes * share, 2)
            decomposicao[trib] = valor_trib

        return CalculoSimplesResultado(
            rbt12=rbt12,
            faturamento_mes=faturamento_mes,
            anexo_aplicado=anexo,
            faixa=faixa.faixa,
            aliquota_nominal=faixa.aliquota_nominal,
            parcela_deduzir=faixa.parcela_deduzir,
            aliquota_efetiva=aliquota_efetiva,
            imposto_mes=imposto_mes,
            decomposicao_tributos=decomposicao,
            fator_r_percentual=fator_r_percentual,
            migrou_anexo_por_fator_r=migrou_fator_r,
        )

    def calcular_custo_mensal_mei(self, cnae: CNAEItem) -> float:
        """Calcula o valor fixo da guia DAS-MEI mensal com base na atividade do CNAE."""
        inss = self.salario_minimo * self.mei_inss_perc
        icms = (
            self.mei_icms_fixo
            if ("ICMS" in cnae.tributos or cnae.anexo_padrao in ["I", "II"])
            else 0.0
        )
        iss = (
            self.mei_iss_fixo
            if ("ISS" in cnae.tributos or cnae.anexo_padrao in ["III", "IV", "V"])
            else 0.0
        )
        return round(inss + icms + iss, 2)

    def simular(
        self,
        cnae_identificador: str,
        faturamento_anual: float,
        folha_anual: float = 0.0,
        faturamento_mensal: Optional[float] = None,
    ) -> SimulacaoComparativaResultado:
        """
        Executa simulação completa para orientação do empreendedor:
        - Validação de CNAE
        - Regra do Fator R
        - Avaliação de enquadramento MEI vs Simples Nacional
        - Cálculo de impostos e economia potencial
        """
        # 1. Recupera CNAE
        cnae = self.repo.get_cnae_by_codigo(cnae_identificador)
        if not cnae:
            # Tenta busca textual
            busca = self.repo.search_cnaes(cnae_identificador, limit=1)
            if busca:
                cnae = busca[0]
            else:
                raise ValueError(f"CNAE '{cnae_identificador}' não encontrado na base fiscal.")

        if faturamento_mensal is None:
            faturamento_mensal = faturamento_anual / 12.0 if faturamento_anual > 0 else 0.0

        alertas = []

        # 2. Avalia Fator R e Anexo
        fator_r = self.calcular_fator_r(folha_anual, faturamento_anual)
        anexo_aplicado, migrou = self.determinar_anexo(cnae, fator_r)

        if cnae.sujeito_fator_r:
            if migrou:
                alertas.append(
                    f"Fator R favorável ({fator_r * 100:.1f}% >= 28%): enquadrado no Anexo III com alíquota reduzida."
                )
            else:
                alertas.append(
                    f"Fator R insuficiente ({fator_r * 100:.1f}% < 28%): tributado no Anexo V (alíquota superior). Avalie folha/pró-labore para atingir 28%."
                )

        # 3. Cálculo Simples Nacional
        simples_res = self.calcular_aliquota_efetiva(
            rbt12=faturamento_anual,
            anexo=anexo_aplicado,
            faturamento_mes=faturamento_mensal,
            fator_r_percentual=fator_r if cnae.sujeito_fator_r else None,
            migrou_fator_r=migrou,
        )

        # 4. Avalia Elegibilidade MEI
        mei_elegivel = True
        mei_motivo = None
        mei_custo = None
        limite_teto_tolerancia = self.limite_mei * (1 + self.tolerancia_mei)

        if not cnae.permitido_mei:
            mei_elegivel = False
            mei_motivo = f"A atividade '{cnae.descricao}' (CNAE {cnae.codigo}) é vedada ao MEI (Resolução CGSN nº 140)."
        elif faturamento_anual > limite_teto_tolerancia:
            mei_elegivel = False
            mei_motivo = (
                f"Faturamento anual (R$ {faturamento_anual:,.2f}) excedeu em mais de 20% o limite do MEI "
                f"(R$ {self.limite_mei:,.2f}). Desenquadramento obrigatório e retroativo ao início do ano."
            )
            alertas.append(mei_motivo)
        elif faturamento_anual > self.limite_mei:
            mei_elegivel = False
            mei_motivo = (
                f"Faturamento anual (R$ {faturamento_anual:,.2f}) superou o teto do MEI de R$ {self.limite_mei:,.2f}, "
                f"mas está na faixa de tolerância de até 20% (até R$ {limite_teto_tolerancia:,.2f}). "
                "O desenquadramento valerá a partir de 1º de janeiro do próximo ano."
            )
            alertas.append(mei_motivo)
        else:
            mei_custo = self.calcular_custo_mensal_mei(cnae)

        # 5. Recomendação e Economia
        economia_mensal = None
        if mei_elegivel and mei_custo is not None:
            recomendacao = "MEI (Microempreendedor Individual)"
            if simples_res.imposto_mes > mei_custo:
                economia_mensal = round(simples_res.imposto_mes - mei_custo, 2)
                alertas.append(
                    f"Como MEI, sua economia estimada é de R$ {economia_mensal:,.2f}/mês frente ao Simples Nacional."
                )
        else:
            recomendacao = f"Simples Nacional ({simples_res.anexo_aplicado})"

        # Alerta de teto do Simples Nacional
        if faturamento_anual > self.limite_simples:
            alertas.append(
                f"Atenção: faturamento anual excede o limite máximo do Simples Nacional (R$ {self.limite_simples:,.2f}). "
                "Empresa obrigada ao Lucro Presumido ou Lucro Real."
            )

        return SimulacaoComparativaResultado(
            cnae=cnae,
            faturamento_anual=faturamento_anual,
            faturamento_mensal=faturamento_mensal,
            folha_12m=folha_anual,
            fator_r=fator_r,
            mei_elegivel=mei_elegivel,
            mei_motivo_inelegibilidade=mei_motivo,
            mei_custo_mensal=mei_custo,
            simples_resultado=simples_res,
            recomendacao_regime=recomendacao,
            economia_mensal_mei=economia_mensal,
            alertas=alertas,
        )
