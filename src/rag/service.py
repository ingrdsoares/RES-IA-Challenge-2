"""
Serviço de RAG e Copiloto Fiscal Factual.
Frente: Ciência de Dados (Jhessica).
Integração: RAG (Legislação) + Motor Determinístico (Lucas) + Guardrails (Clara e Nasser).
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.fiscal.calculator import FiscalCalculator
from src.fiscal.repository import FiscalRepository
from src.rag.entity_extractor import TaxEntityExtractor
from src.rag.prompts import (
    DISCLAIMER_CRC_PADRAO,
    PROMPT_ABSTENCAO_MOTIVO,
)
from src.rag.vector_store import LegalVectorStore


@dataclass
class RespostaCopiloto:
    pergunta: str
    diagnostico: str
    plano_3_passos: List[str]
    fontes_citadas: List[Dict[str, Any]]
    calculo_detalhado: Optional[Dict[str, Any]] = None
    se_absteve: bool = False
    motivo_abstencao: Optional[str] = None
    disclaimer_crc: str = DISCLAIMER_CRC_PADRAO
    score_confianca: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RAGService:
    """
    Serviço central de IA generativa factual e roteamento de regularização tributária.
    Une recuperação vetorial jurídica, cálculo determinístico de impostos e guardrails anti-alucinação.
    """

    TERMOS_ABSTENCAO = [
        "sonegar",
        "sonegação",
        "esconder receita",
        "nota calçada",
        "fraudar",
        "lavagem de dinheiro",
        "crime fiscal",
        "lucro real complexo",
        "holding offshore",
        "inventário judicial",
        "processo penal",
    ]

    def __init__(
        self,
        vector_store: Optional[LegalVectorStore] = None,
        calculator: Optional[FiscalCalculator] = None,
        extractor: Optional[TaxEntityExtractor] = None,
        base_dir: Optional[Path] = None,
    ):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent.parent
        else:
            self.base_dir = Path(base_dir)

        # 1. Inicializa Vector Store se não for injetado
        if vector_store:
            self.vector_store = vector_store
        else:
            db_path = self.base_dir / "data" / "processed" / "vector_index.db"
            self.vector_store = LegalVectorStore(db_path=str(db_path), use_dense=True)

        # 2. Inicializa Motor Fiscal se não for injetado
        if calculator:
            self.calculator = calculator
        else:
            fiscal_db = self.base_dir / "data" / "processed" / "fiscal.db"
            if fiscal_db.exists():
                repo = FiscalRepository(db_path=str(fiscal_db))
                self.calculator = FiscalCalculator(repository=repo)
            else:
                self.calculator = None

        # 3. Inicializa Extrator de Entidades Fiscais
        self.extractor = extractor or TaxEntityExtractor()

    def _verificar_gatilho_abstencao(self, pergunta: str) -> Optional[str]:
        """Detecta se a pergunta fere as diretrizes éticas ou ultrapassa o escopo do Simples Nacional."""
        p_lower = pergunta.lower()
        for termo in self.TERMOS_ABSTENCAO:
            if termo in p_lower:
                return PROMPT_ABSTENCAO_MOTIVO["fora_de_escopo"]
        return None

    def consultar(
        self,
        pergunta: str,
        cnae: Optional[str] = None,
        faturamento_anual: Optional[float] = None,
        folha_anual: Optional[float] = None,
    ) -> RespostaCopiloto:
        """
        Ponto de entrada do Copiloto Fiscal:
        1. Avalia guardrails e abstenção proativa.
        2. Extrai entidades e expande a busca vetorial.
        3. Recupera dispositivos legais canônicos no Vector Store.
        4. Aciona cálculo determinístico se houver contexto fiscal.
        5. Sintetiza o diagnóstico e o Plano de Ação em 3 Passos.
        """
        # 1. Guardrail de Abstenção
        motivo_abstencao = self._verificar_gatilho_abstencao(pergunta)
        if motivo_abstencao:
            return RespostaCopiloto(
                pergunta=pergunta,
                diagnostico="Esta solicitação ultrapassa o escopo de atuação do Sócio Digital para orientações ordinárias de MEI e Simples Nacional.",
                plano_3_passos=[
                    "Passo 1 (Paralisação): Interromper qualquer ação sem fundamentação formal expressa.",
                    "Passo 2 (Consulta Presencial): Agendar atendimento técnico imediato com escritório contábil habilitado (CRC).",
                    "Passo 3 (Auditoria Jurídica): Se envolver passivo contencioso, buscar assessoria jurídica especializada em Direito Tributário."
                ],
                fontes_citadas=[{
                    "norma": "Código de Ética Profissional do Contador e Resolução CFC nº 803/1996",
                    "artigo": "Diretriz Geral",
                    "trecho": "Prerrogativa privativa de atendimento contábil pericial e conformidade estrita com a lei."
                }],
                se_absteve=True,
                motivo_abstencao=motivo_abstencao,
                score_confianca=1.0,
            )

        # 2. Extração Factual de Entidades e Expansão da Consulta
        extracted = self.extractor.extract(pergunta)
        if cnae is None and extracted.cnaes:
            cnae = extracted.cnaes[0]["codigo"]
        if faturamento_anual is None and "rbt12" in extracted.parametros_calculo:
            faturamento_anual = extracted.parametros_calculo["rbt12"]
        if folha_anual is None and "folha_12m" in extracted.parametros_calculo:
            folha_anual = extracted.parametros_calculo["folha_12m"]

        # 3. Recuperação Factual no Vector Store (RAG)
        search_query = extracted.query_expandida if extracted.query_expandida else pergunta
        retrieved_chunks = self.vector_store.search(search_query, top_k=3)
        score_maximo = retrieved_chunks[0]["score"] if retrieved_chunks else 0.0

        # Se a busca vetorial tiver relevância quase nula e a pergunta não tiver contexto
        if score_maximo < 0.15 and not cnae:
            return RespostaCopiloto(
                pergunta=pergunta,
                diagnostico="Não foi localizada fundamentação suficiente na base legal indexada para responder a sua dúvida com segurança absoluta.",
                plano_3_passos=[
                    "Passo 1 (Refinamento): Reformule a pergunta fornecendo a atividade (CNAE) ou o regime tributário da empresa.",
                    "Passo 2 (Consulta Oficial): Verifique o portal do Simples Nacional ou manuais de perguntas frequentes da Receita Federal.",
                    "Passo 3 (Validação Contábil): Submeta a dúvida ao seu contador para análise das particularidades do seu município."
                ],
                fontes_citadas=[],
                se_absteve=True,
                motivo_abstencao=PROMPT_ABSTENCAO_MOTIVO["sem_base_oficial"],
                score_confianca=round(score_maximo, 4),
            )

        # 3. Execução Determinística de Cálculo (se aplicável)
        resultado_calculo = None
        if self.calculator and cnae and faturamento_anual is not None:
            try:
                folha = folha_anual or 0.0
                sim_res = self.calculator.simular(
                    cnae_identificador=cnae,
                    faturamento_anual=faturamento_anual,
                    folha_anual=folha,
                )
                resultado_calculo = {
                    "cnae": sim_res.cnae.codigo,
                    "cnae_descricao": sim_res.cnae.descricao,
                    "faturamento_anual": sim_res.faturamento_anual,
                    "folha_anual": sim_res.folha_12m,
                    "fator_r": sim_res.fator_r,
                    "anexo_aplicado": sim_res.simples_resultado.anexo_aplicado,
                    "aliquota_efetiva": sim_res.simples_resultado.aliquota_efetiva,
                    "das_mensal": sim_res.simples_resultado.imposto_mes,
                    "mei_elegivel": sim_res.mei_elegivel,
                    "mei_motivo": sim_res.mei_motivo_inelegibilidade,
                    "recomendacao_regime": sim_res.recomendacao_regime,
                    "economia_mensal": sim_res.economia_mensal_mei or (
                        sim_res.simples_resultado.imposto_mes if sim_res.simples_resultado.migrou_anexo_por_fator_r else 0.0
                    ),
                    "alertas": sim_res.alertas,
                }
            except Exception as e:
                resultado_calculo = {"erro_calculo": str(e)}

        # 4. Formatação de Citações Oficiais
        fontes_formatadas = []
        for ch in retrieved_chunks:
            fontes_formatadas.append({
                "artigo": ch.get("artigo"),
                "paragrafo": ch.get("paragrafo"),
                "norma": ch.get("source_doc"),
                "tema": ch.get("tema"),
                "trecho": ch.get("raw_text")[:240].strip() + "...",
                "score": ch.get("score"),
            })

        # 5. Síntese do Diagnóstico e do Plano de 3 Passos
        diagnostico, plano = self._sintetizar_resposta(
            pergunta=pergunta,
            retrieved=retrieved_chunks,
            calc=resultado_calculo,
        )

        return RespostaCopiloto(
            pergunta=pergunta,
            diagnostico=diagnostico,
            plano_3_passos=plano,
            fontes_citadas=fontes_formatadas,
            calculo_detalhado=resultado_calculo,
            se_absteve=False,
            score_confianca=round(score_maximo, 4),
        )

    def _sintetizar_resposta(
        self,
        pergunta: str,
        retrieved: List[Dict[str, Any]],
        calc: Optional[Dict[str, Any]],
    ) -> tuple[str, List[str]]:
        """
        Sintetiza de forma didática o diagnóstico e o roteiro prático em 3 passos.
        Garante zero alucinação combinando dados do motor determinístico e chunks legais.
        """
        p_lower = pergunta.lower()
        top_artigo = retrieved[0]["artigo"] if retrieved else "Legislação Tributária"

        # CENÁRIO A: Fator R e Anexo III vs V
        if "fator r" in p_lower or (calc and calc.get("fator_r") is not None and calc.get("fator_r") > 0):
            if calc and "anexo_aplicado" in calc:
                fator_perc = calc["fator_r"] * 100
                anexo = calc["anexo_aplicado"]
                aliq = calc["aliquota_efetiva"] * 100
                das = calc["das_mensal"]

                if fator_perc >= 28.0:
                    diag = (
                        f"Ótima notícia! Pelos dados apurados, seu Fator R atingiu {fator_perc:.1f}% (superior ao mínimo legal de 28%). "
                        f"A sua empresa tributa pelo Anexo III do Simples Nacional, resultando em uma alíquota efetiva de {aliq:.2f}% "
                        f"(guia DAS mensal estimada em R$ {das:,.2f}), garantindo a menor tributação legal para serviços."
                    )
                    plano = [
                        "Passo 1 (Parametrização): Informar ao escritório de contabilidade o fechamento exato da folha de salários e pró-labore até o dia 05 para cômputo dos 12 meses anteriores.",
                        "Passo 2 (Apuração PGDAS-D): No momento da emissão no portal da Receita Federal, certificar-se de que as receitas foram segregadas no campo 'Serviços sujeitos ao Fator R tributados no Anexo III'.",
                        "Passo 3 (Comprovação): Arquivar o Extrato do Simples Nacional demonstrando a alíquota de 8,08% e a memória de cálculo para resguardo em caso de fiscalização."
                    ]
                else:
                    diag = (
                        f"Atenção ao seu enquadramento: seu Fator R calculado é de {fator_perc:.1f}% (abaixo do patamar de 28%). "
                        f"Dessa forma, a atividade é temporariamente tributada pelo Anexo V ({aliq:.2f}%), gerando uma guia DAS de R$ {das:,.2f}."
                    )
                    plano = [
                        "Passo 1 (Análise de Viabilidade): Avaliar junto ao seu contador o aumento do pró-labore dos sócios para elevar a razão da folha acima de 28%.",
                        "Passo 2 (Simulação de Encargos): Comparar se o custo previdenciário do pró-labore (INSS de 11%) é inferior à economia gerada no DAS ao migrar para o Anexo III.",
                        "Passo 3 (Adequação da Folha): Registrar o ajuste contábil no eSocial para refletir a nova média nos meses subsequentes."
                    ]
                return diag, plano

        # CENÁRIO B: MEI e Desenquadramento por Excesso de Faturamento
        if "mei" in p_lower and ("desenquadr" in p_lower or "20%" in p_lower or "limite" in p_lower or "faturei" in p_lower):
            if calc and not calc.get("mei_elegivel"):
                motivo = calc.get("mei_motivo", "")
                diag = f"Alerta de Desenquadramento Fiscal do MEI: {motivo} Conforme o {top_artigo} da LC 123/2006, o limite anual do MEI é de R$ 81.000,00."
            else:
                diag = (
                    f"A regra de faturamento do MEI (LC 123/2006, {top_artigo}) divide-se em dois cenários: "
                    f"1) Excesso de até 20% (até R$ 97.200,00): desenquadramento a partir de 1º de janeiro do ano seguinte com pagamento de DAS complementar; "
                    f"2) Excesso acima de 20% (acima de R$ 97.200,00): desenquadramento imediato e retroativo a janeiro do ano corrente, com recolhimento como Microempresa (ME) no Simples."
                )

            plano = [
                "Passo 1 (Diagnóstico do Excesso): Somar todas as notas fiscais emitidas no ano e o faturamento sem nota para identificar se o excesso superou ou não os 20% de tolerância.",
                "Passo 2 (Comunicação Obrigatória): Acessar o Portal do Simples Nacional (Serviços SIMEI) e registrar a 'Comunicação de Desenquadramento Obrigatório'.",
                "Passo 3 (Migração para Microempresa): Contratar um profissional contábil para elaborar o contrato social, adequar os livros fiscais e apurar os tributos como ME."
            ]
            return diag, plano

        # CENÁRIO C: Regularidade Fiscal e Certidões (CND / CPEN)
        if "certidão" in p_lower or "cnd" in p_lower or "cpen" in p_lower or "débito" in p_lower or "parcela" in p_lower:
            diag = (
                f"A regularidade fiscal da empresa é atestada pela Certidão Negativa de Débitos (CND) ou pela "
                f"Certidão Positiva com Efeitos de Negativa (CPEN). Conforme a Receita Federal ({top_artigo}), "
                f"a adesão a um parcelamento tributário formal ativo com parcelas em dia suspende a exigibilidade do crédito e autoriza a emissão imediata da CPEN, permitindo à empresa continuar operando e emitindo notas."
            )
            plano = [
                "Passo 1 (Consulta de Pendências): Acessar o Portal e-CAC da Receita Federal com certificado digital ou conta Gov.br (Prata/Ouro) e emitir a 'Situação Fiscal'.",
                "Passo 2 (Negociação e Parcelamento): Optar pelo Programa de Parcelamento Ordinário do Simples Nacional ou Transação Tributária na PGFN (Regularize), efetuando o pagamento da primeira parcela.",
                "Passo 3 (Emissão da CPEN): Aguardar a compensação bancária (24 a 48h) e emitir a Certidão Positiva com Efeitos de Negativa no site da Receita Federal."
            ]
            return diag, plano

        # CENÁRIO C2: Cálculo Geral do Simples Nacional (Comércio, Indústria e Serviços sem Fator R)
        if calc and "anexo_aplicado" in calc:
            anexo = calc["anexo_aplicado"]
            aliq = calc["aliquota_efetiva"] * 100
            das = calc["das_mensal"]
            cnae_desc = calc.get("cnae_descricao") or "Atividade econômica informada"
            cnae_cod = calc.get("cnae") or ""
            diag = (
                f"Para a atividade de {cnae_desc} (CNAE {cnae_cod}) com faturamento anual informado, a tributação ocorre pelo "
                f"Anexo {anexo} do Simples Nacional. A alíquota efetiva apurada conforme o {top_artigo} da LC 123/2006 "
                f"é de {aliq:.2f}%, resultando em uma guia DAS mensal estimada de R$ {das:,.2f}."
            )
            plano = [
                f"Passo 1 (Apuração da Receita): Segregar as receitas brutas da competência corrente correspondentes ao Anexo {anexo} a partir das notas fiscais emitidas.",
                f"Passo 2 (Emissão do DAS no PGDAS-D): Acessar o Portal do Simples Nacional até o dia 20 do mês subsequente, preenchendo a apuração para emissão da guia única com alíquota de {aliq:.2f}%.",
                "Passo 3 (Conciliação Contábil): Acompanhar o acumulado dos 12 meses anteriores (RBT12) para monitorar eventuais mudanças de faixa de tributação e arquivar o extrato oficial."
            ]
            return diag, plano

        # CENÁRIO D: Dúvida Geral Normativa
        diag = (
            f"Com base na legislação tributária oficial ({top_artigo} e normas correlatas), sua dúvida foi analisada no contexto de micro e pequenas empresas. "
            f"A conformidade exige a observância rigorosa das regras do Simples Nacional para evitar autuações fiscais."
        )
        plano = [
            f"Passo 1 (Conferência Legal): Revisar os requisitos expressos no {top_artigo} e confrontá-los com o histórico contábil da sua empresa.",
            "Passo 2 (Organização Documental): Reunir notas fiscais, extratos bancários e guias pagas pertinentes à operação.",
            "Passo 3 (Validação Técnica): Alinhar o procedimento adotado junto ao seu profissional contábil habilitado (CRC)."
        ]
        return diag, plano
