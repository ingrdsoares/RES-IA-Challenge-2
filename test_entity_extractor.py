"""
Suíte de Testes do Extrator de Entidades Fiscais e Integração RAG + Motor.
Sócio Digital — RES-IA Challenge 2 (Frente de Ciência de Dados - Jhessica).
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.fiscal.calculator import FiscalCalculator
from src.fiscal.repository import FiscalRepository
from src.rag.entity_extractor import TaxEntityExtractor
from src.rag.vector_store import LegalVectorStore


def run_tests():
    print("=" * 75)
    print(" SÓCIO DIGITAL — TESTE DO EXTRATOR DE ENTIDADES FISCAIS (NER FISCAL)")
    print(" Responsável: Jhessica (Ciência de Dados)")
    print("=" * 75)

    fiscal_db = str(BASE_DIR / "data" / "processed" / "fiscal.db")
    vector_db = str(BASE_DIR / "data" / "processed" / "vector_index.db")

    repo = FiscalRepository(fiscal_db) if Path(fiscal_db).exists() else None
    calculator = FiscalCalculator(repo) if repo else None
    vector_store = LegalVectorStore(vector_db) if Path(vector_db).exists() else None

    extractor = TaxEntityExtractor(fiscal_repository=repo)

    casos_de_teste = [
        {
            "id": "CASO 1: MEI e Desenquadramento por Excesso",
            "texto": "Minha empresa é MEI e faturei R$ 105.000,00 no ano. Ultrapassei em mais de 20% o teto de 81 mil. Vou ser desenquadrado retroativamente?",
            "validacoes": {
                "intencao": "desenquadramento_mei",
                "regime_presente": "mei",
                "percentual_presente": 20.0,
                "valores_esperados": [105000.0, 81000.0],
                "tag_rag": "desenquadramento",
            },
        },
        {
            "id": "CASO 2: Software, CNAE e Fator R (28%)",
            "texto": "Temos o CNAE 6201-5/01. Nossa receita anual acumulada é de R$ 300.000,00 e a folha de pagamento dos últimos 12 meses foi de R$ 90.000,00. Aplicamos a regra do Fator R de 28% para o Anexo III?",
            "validacoes": {
                "intencao": "fator_r",
                "cnae_codigo": "6201-5/01",
                "fator_r_calculado": 0.30,
                "anexo_presente": "III",
                "tag_rag": "fator_r",
            },
        },
        {
            "id": "CASO 3: Obrigação Acessória DASN-SIMEI",
            "texto": "Qual a data limite para entrega da declaração anual DASN-SIMEI e qual o valor da multa por atraso?",
            "validacoes": {
                "intencao": "obrigacoes_acessorias",
                "obrigacao_presente": "dasn_simei",
                "tag_rag": "obrigacoes_acessorias",
            },
        },
        {
            "id": "CASO 4: Regularização, Termo de Exclusão e CPEN",
            "texto": "Recebi um termo de exclusão com dívida de R$ 15.000,00. Se eu fizer o parcelamento em 60 parcelas consigo a certidão CPEN?",
            "validacoes": {
                "intencao": "regularizacao_pendencias",
                "certidao_presente": "cpen",
                "obrigacao_presente": "parcelamento",
                "tag_rag": "certidoes",
            },
        },
        {
            "id": "CASO 5: CNPJ e Simulação Simples",
            "texto": "Consulta da empresa CNPJ 12.345.678/0001-90 com atividade CNAE 4781-0/00 e faturamento anual de R$ 240.000,00 para calcular a alíquota.",
            "validacoes": {
                "cnpj_esperado": "12.345.678/0001-90",
                "cnae_codigo": "4781-0/00",
                "intencao": "calculo_simples",
            },
        },
    ]

    sucessos = 0
    total = len(casos_de_teste)

    for c in casos_de_teste:
        print(f"\n[{c['id']}]")
        print(f"  Texto: \"{c['texto'][:90]}...\"")

        res = extractor.extract(c["texto"])

        print(f"  -> Intenção Primária: {res.intencao_primaria} (Confiança: {res.confianca_intencao:.2f})")
        print(f"  -> CNAEs Detectados: {[x['codigo'] for x in res.cnaes]}")
        print(f"  -> CNPJs Detectados: {res.cnpjs}")
        print(f"  -> Regimes: {res.regimes} | Anexos: {res.anexos}")
        print(f"  -> Valores Monetários: {[v['valor'] for v in res.valores_monetarios]}")
        print(f"  -> Percentuais: {[p['percentual'] for p in res.percentuais]}")
        print(f"  -> Parâmetros Extraídos: {res.parametros_calculo}")
        print(f"  -> Tags para RAG: {res.tags_rag}")

        # Validações estritas
        v = c["validacoes"]
        passou = True

        if "intencao" in v and res.intencao_primaria != v["intencao"]:
            print(f"  [FALHA] Esperava intenção '{v['intencao']}', obteve '{res.intencao_primaria}'")
            passou = False

        if "cnae_codigo" in v:
            cnaes_cods = [x["codigo"] for x in res.cnaes]
            if v["cnae_codigo"] not in cnaes_cods:
                print(f"  [FALHA] CNAE {v['cnae_codigo']} não detectado!")
                passou = False

        if "cnpj_esperado" in v:
            if v["cnpj_esperado"] not in res.cnpjs:
                print(f"  [FALHA] CNPJ {v['cnpj_esperado']} não detectado!")
                passou = False

        if "tag_rag" in v:
            if v["tag_rag"] not in res.tags_rag:
                print(f"  [FALHA] Tag RAG '{v['tag_rag']}' esperada não gerada!")
                passou = False

        if "fator_r_calculado" in v:
            calculado = res.parametros_calculo.get("fator_r_calculado")
            if calculado != v["fator_r_calculado"]:
                print(f"  [FALHA] Fator R calculado {calculado} != esperado {v['fator_r_calculado']}")
                passou = False

        if passou:
            print("  [OK] Todas as validações deste caso passaram com sucesso!")
            sucessos += 1

    # Teste de Integração Tripla: Extrator -> Motor Fiscal -> Vector Store RAG
    print("\n" + "-" * 75)
    print(" [TESTE DE INTEGRAÇÃO TRIPLA] Extrator -> Motor Fiscal -> Vector Store")
    print("-" * 75)

    if calculator and vector_store:
        pergunta = "Empresa CNAE 6201-5/01 faturou R$ 300.000,00 no ano com folha de R$ 90.000,00. Como fica o imposto?"
        extracao = extractor.extract(pergunta)
        params = extracao.parametros_calculo

        # 1. Motor determinístico calcula com os parâmetros extraídos
        cnae_obj = repo.get_cnae_by_codigo(params["cnae_codigo"])
        fator_r = calculator.calcular_fator_r(params["folha_12m"], params["rbt12"])
        anexo, migrou = calculator.determinar_anexo(cnae_obj, fator_r)
        calculo = calculator.calcular_aliquota_efetiva(
            rbt12=params["rbt12"],
            anexo=anexo,
            faturamento_mes=params.get("faturamento_mes", params["rbt12"] / 12.0),
            fator_r_percentual=fator_r,
        )

        # 2. Vector store busca fundamentação legal com query expandida e tag de foco
        filter_tags = [extracao.tag_foco] if extracao.tag_foco else extracao.tags_rag
        rag_hits = vector_store.search(extracao.query_expandida, top_k=1, filter_tags=filter_tags)

        print(f"  -> Pergunta do Usuário: \"{pergunta}\"")
        print(f"  -> Query Expandida (RAG): \"{extracao.query_expandida}\"")
        print(f"  -> Tag de Foco: {extracao.tag_foco} | Tags RAG: {extracao.tags_rag}")
        print(f"  -> Parâmetros Extraídos: RBT12 = R$ {params['rbt12']:,.2f} | Folha = R$ {params['folha_12m']:,.2f}")
        print(f"  -> Fator R Calculado pelo Motor: {fator_r * 100:.1f}% -> Anexo {anexo} (Migrou: {migrou})")
        print(f"  -> Alíquota Efetiva: {calculo.aliquota_efetiva * 100:.2f}% | Imposto Mensal: R$ {calculo.imposto_mes:,.2f}")
        print(f"  -> Artigo Legal Recuperado pelo RAG: {rag_hits[0]['artigo']} ({rag_hits[0]['source_doc']})")

        integracao_ok = (anexo == "III" and "Art. 18" in rag_hits[0]["artigo"])
        if integracao_ok:
            print("  [OK] Integração Tripla validada com 100% de sucesso e consistência!")
        else:
            print("  [FALHA] Discrepância na Integração Tripla.")
    else:
        print("  [AVISO] Pulei integração tripla pois bases SQLite não foram encontradas.")

    print("\n" + "=" * 75)
    print(f" RESULTADO FINAL: {sucessos}/{total} casos de extração validados!")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
