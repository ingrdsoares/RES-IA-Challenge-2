"""
Suite de Testes e Validação do Módulo Fiscal (CNAEs e Tabelas do Simples Nacional).
Sócio Digital — RES-IA Challenge 2 (Lucas - Engenharia de Dados & Dev).
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.fiscal.calculator import FiscalCalculator
from src.fiscal.ingest import FiscalIngestionPipeline
from src.fiscal.repository import FiscalRepository


def run_fiscal_validation():
    print("=" * 75)
    print(" SÓCIO DIGITAL — TESTE DE INGESTÃO E MOTOR DETERMINÍSTICO FISCAL")
    print(" Responsável: Lucas (Engenharia de Dados & Dev)")
    print("=" * 75)

    raw_tabelas = str(BASE_DIR / "data" / "raw" / "tabelas_simples_nacional.json")
    raw_cnaes = str(BASE_DIR / "data" / "raw" / "cnaes_base.json")
    db_path = str(BASE_DIR / "data" / "processed" / "fiscal.db")
    manifest_path = str(BASE_DIR / "data" / "processed" / "fiscal_manifest.json")

    # -------------------------------------------------------------
    # 1. Executa Ingestão
    # -------------------------------------------------------------
    print("\n[Etapa 1] Executando Ingestão de Dados Fiscais...")
    pipeline = FiscalIngestionPipeline(
        raw_tabelas_path=raw_tabelas,
        raw_cnaes_path=raw_cnaes,
        db_path=db_path,
        manifest_path=manifest_path,
    )
    manifest = pipeline.run()

    stats = manifest.get("stats", {})
    print(
        f" -> Anexos Indexados: {stats.get('total_anexos')} ({', '.join(stats.get('anexos_disponiveis', []))})"
    )
    print(f" -> Total de Faixas Fiscais: {stats.get('total_faixas')}")
    print(f" -> Total de CNAEs Catalogados: {stats.get('total_cnaes')}")
    print(f" -> CNAEs Permitidos no MEI: {stats.get('total_cnaes_permitidos_mei')}")
    print(f" -> CNAEs Sujeitos ao Fator R: {stats.get('total_cnaes_sujeitos_fator_r')}")

    # -------------------------------------------------------------
    # 2. Inicializa Repositório e Motor de Cálculo
    # -------------------------------------------------------------
    repo = FiscalRepository(db_path=db_path)
    calc = FiscalCalculator(repository=repo)

    sucessos = 0
    total_testes = 0

    # -------------------------------------------------------------
    # 3. Teste de Busca e Resolução de CNAE
    # -------------------------------------------------------------
    print("\n[Etapa 2] Validando Busca e Resolução de CNAEs:")
    print("-" * 75)

    total_testes += 1
    cnae_ti = repo.get_cnae_by_codigo("6201-5/01")
    if (
        cnae_ti
        and cnae_ti.anexo_padrao == "V"
        and cnae_ti.sujeito_fator_r
        and not cnae_ti.permitido_mei
    ):
        print(
            "  [OK] CNAE 6201-5/01 (Software): Resolvido corretamente (Anexo V, Fator R=Sim, MEI=Não)"
        )
        sucessos += 1
    else:
        print("  [FALHA] Falha na resolução do CNAE 6201-5/01")

    total_testes += 1
    busca_texto = repo.search_cnaes("eletricista", limit=1)
    if busca_texto and "4321-5/00" in busca_texto[0].codigo and busca_texto[0].permitido_mei:
        print(
            f"  [OK] Busca FTS5 por 'eletricista': Encontrou {busca_texto[0].codigo} ({busca_texto[0].ocupacao_mei})"
        )
        sucessos += 1
    else:
        print("  [FALHA] Busca FTS5 por 'eletricista' falhou")

    # -------------------------------------------------------------
    # 4. Caso Canônico 1: Comércio Varejista (Anexo I - Faixa 2)
    # -------------------------------------------------------------
    print("\n[Etapa 3] Casos Canônicos de Simulação Tributária Determinística:")
    print("-" * 75)

    print("\n[Caso 1] Comércio Varejista de Roupas (CNAE 4781-0/00)")
    print("  Faturamento Anual RBT12: R$ 240.000,00 | Mensal: R$ 20.000,00")
    total_testes += 1
    sim_comercio = calc.simular("4781-0/00", faturamento_anual=240000.00)
    res_com = sim_comercio.simples_resultado

    # Alíquota efetiva esperada: ((240.000 * 0.073) - 5.940) / 240.000 = 11.580 / 240.000 = 4.825% (0.0483 ou 0.0482)
    print(f"  -> Anexo: {res_com.anexo_aplicado} (Faixa {res_com.faixa})")
    print(
        f"  -> Alíquota Nominal: {res_com.aliquota_nominal * 100:.2f}% | Parcela a Deduzir: R$ {res_com.parcela_deduzir:,.2f}"
    )
    print(f"  -> Alíquota Efetiva: {res_com.aliquota_efetiva * 100:.2f}%")
    print(f"  -> DAS Mensal Estimado: R$ {res_com.imposto_mes:,.2f}")
    print(
        f"  -> Decomposição: ICMS: R$ {res_com.decomposicao_tributos.get('ICMS', 0):,.2f} | CPP: R$ {res_com.decomposicao_tributos.get('CPP', 0):,.2f}"
    )

    if res_com.faixa == 2 and 0.0480 <= res_com.aliquota_efetiva <= 0.0485:
        print("  [OK] Cálculo determinístico do Anexo I executado com 100% de exatidão!")
        sucessos += 1
    else:
        print(f"  [FALHA] Alíquota efetiva incorreta: {res_com.aliquota_efetiva}")

    # -------------------------------------------------------------
    # 5. Caso Canônico 2: Empresa de TI com Fator R >= 28%
    # -------------------------------------------------------------
    print("\n[Caso 2] Empresa de Software (CNAE 6201-5/01) com Fator R >= 28%")
    print("  Faturamento Anual RBT12: R$ 300.000,00 | Folha 12m: R$ 90.000,00 (Fator R = 30%)")
    total_testes += 1
    sim_ti_com_folha = calc.simular("6201-5/01", faturamento_anual=300000.00, folha_anual=90000.00)
    res_ti_folha = sim_ti_com_folha.simples_resultado

    # Fator R = 90k / 300k = 30% >= 28% -> Deve migrar para Anexo III!
    # Anexo III Faixa 2: ((300000 * 0.112) - 9360) / 300000 = (33600 - 9360) / 300000 = 24240 / 300000 = 8.08%
    print(f"  -> Fator R Calculado: {sim_ti_com_folha.fator_r * 100:.1f}%")
    print(
        f"  -> Anexo Aplicado: {res_ti_folha.anexo_aplicado} (Migrou por Fator R: {res_ti_folha.migrou_anexo_por_fator_r})"
    )
    print(f"  -> Alíquota Efetiva: {res_ti_folha.aliquota_efetiva * 100:.2f}%")
    print(f"  -> DAS Mensal: R$ {res_ti_folha.imposto_mes:,.2f}")

    # Comparação se estivesse no Anexo V (sem folha suficiente):
    sim_ti_sem_folha = calc.simular("6201-5/01", faturamento_anual=300000.00, folha_anual=30000.00)
    res_ti_sem = sim_ti_sem_folha.simples_resultado
    economia_fator_r = res_ti_sem.imposto_mes - res_ti_folha.imposto_mes
    print(
        f"  -> Se estivesse no Anexo V (folha 10%): DAS seria R$ {res_ti_sem.imposto_mes:,.2f} ({res_ti_sem.aliquota_efetiva * 100:.2f}%)"
    )
    print(
        f"  -> Economia gerada pela aplicação do Fator R: R$ {economia_fator_r:,.2f}/mês (R$ {economia_fator_r * 12:,.2f}/ano)"
    )

    if (
        res_ti_folha.anexo_aplicado == "III"
        and res_ti_folha.migrou_anexo_por_fator_r
        and 0.0805 <= res_ti_folha.aliquota_efetiva <= 0.0810
    ):
        print(
            "  [OK] Regra do Fator R aplicada com perfeição: migração de Anexo V para Anexo III comprovada!"
        )
        sucessos += 1
    else:
        print(f"  [FALHA] Falha na migração do Fator R: {res_ti_folha.anexo_aplicado}")

    # -------------------------------------------------------------
    # 6. Caso Canônico 3: MEI Elegível (Cabeleireiro)
    # -------------------------------------------------------------
    print("\n[Caso 3] Salão de Beleza / Cabeleireiro (CNAE 9602-5/01)")
    print("  Faturamento Anual: R$ 60.000,00 (R$ 5.000,00/mês)")
    total_testes += 1
    sim_mei = calc.simular("9602-5/01", faturamento_anual=60000.00)

    print(f"  -> MEI Elegível: {sim_mei.mei_elegivel}")
    print(f"  -> Guia DAS-MEI Fixa Mensal: R$ {sim_mei.mei_custo_mensal:,.2f}")
    print(f"  -> Simples Nacional Equivalente: R$ {sim_mei.simples_resultado.imposto_mes:,.2f}/mês")
    print(f"  -> Recomendação: {sim_mei.recomendacao_regime}")
    print(f"  -> Economia Mensal no MEI: R$ {sim_mei.economia_mensal_mei:,.2f}/mês")

    if (
        sim_mei.mei_elegivel
        and sim_mei.mei_custo_mensal == 75.60
        and sim_mei.recomendacao_regime.startswith("MEI")
    ):
        print("  [OK] Diagnóstico MEI e cálculo da guia fixa (INSS + ISS) validados!")
        sucessos += 1
    else:
        print(
            f"  [FALHA] Diagnóstico MEI incorreto: elegível={sim_mei.mei_elegivel}, custo={sim_mei.mei_custo_mensal}"
        )

    # -------------------------------------------------------------
    # 7. Caso Canônico 4: Desenquadramento de MEI por Excesso de Faturamento (> 20%)
    # -------------------------------------------------------------
    print("\n[Caso 4] Desenquadramento de MEI por Excesso de Faturamento")
    print(
        "  Atividade: Cabeleireiro (CNAE 9602-5/01) com Faturamento R$ 105.000,00 (> R$ 97.200,00)"
    )
    total_testes += 1
    sim_desenquadra = calc.simular("9602-5/01", faturamento_anual=105000.00)

    print(f"  -> MEI Elegível: {sim_desenquadra.mei_elegivel}")
    print(f"  -> Motivo: {sim_desenquadra.mei_motivo_inelegibilidade}")
    print(f"  -> Recomendação: {sim_desenquadra.recomendacao_regime}")

    if (
        not sim_desenquadra.mei_elegivel
        and "mais de 20%" in sim_desenquadra.mei_motivo_inelegibilidade
    ):
        print(
            "  [OK] Regra de excesso de faturamento > 20% com desenquadramento retroativo validada!"
        )
        sucessos += 1
    else:
        print("  [FALHA] Validação de excesso de faturamento MEI falhou.")

    print("\n" + "=" * 75)
    print(
        f" RESULTADO FINAL DO MOTOR FISCAL: {sucessos}/{total_testes} testes passaram com sucesso!"
    )
    print("=" * 75)


if __name__ == "__main__":
    run_fiscal_validation()
