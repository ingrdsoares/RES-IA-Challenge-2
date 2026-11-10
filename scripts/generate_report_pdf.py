#!/usr/bin/env python3
"""
Gerador de PDF Oficial: Sócio Digital — Relatório do Projeto, RAG e MLOps.
Residência em Inteligência Artificial (RES-IA) — Challenge 2 (Grupo 08).
Documento estruturado exatamente em 4 páginas executivas de alta densidade e acabamento gráfico.
"""

import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """
    Canvas de duas passadas para calcular dinamicamente o total de páginas
    e desenhar cabeçalhos e rodapés consistentes em todas as páginas.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, total_pages):
        self.saveState()

        # Cabeçalho (a partir da página 2)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#1E3A8A"))
            self.drawString(38, 814, "SÓCIO DIGITAL: COPILOTO DE GESTÃO FISCAL")
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawRightString(557, 814, "RES-IA Challenge 2 | Grupo 08 — Relatório Consolidado")

            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(38, 808, 557, 808)

        # Rodapé (em todas as páginas)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(38, 38, 557, 38)

        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(
            38, 28, "Documento Técnico: Definição do Projeto, Arquitetura RAG e Governança MLOps"
        )
        page_str = f"Página {self._pageNumber} de {total_pages}"
        self.drawRightString(557, 28, page_str)

        self.restoreState()


def create_callout(
    text: str, title: str = "", border_color="#2563EB", bg_color="#EFF6FF", width=519
):
    """Gera um card visual estilizado para destaques ou disclaimers."""
    content = []
    if title:
        title_p = Paragraph(
            f"<b>{title}</b>",
            ParagraphStyle(
                "CalloutTitle",
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11.5,
                textColor=colors.HexColor(border_color),
            ),
        )
        content.append(title_p)
        content.append(Spacer(1, 2))

    body_p = Paragraph(
        text,
        ParagraphStyle(
            "CalloutBody",
            fontName="Helvetica",
            fontSize=7.8,
            leading=10.8,
            textColor=colors.HexColor("#1E293B"),
        ),
    )
    content.append(body_p)

    t = Table([[content]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg_color)),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor(border_color)),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=38,
        rightMargin=38,
        topMargin=40,
        bottomMargin=46,
    )

    c_primary = colors.HexColor("#1E3A8A")  # Azul Marinho Escuro
    c_secondary = colors.HexColor("#0284C7")  # Azul Acento
    c_dark = colors.HexColor("#0F172A")  # Texto Quase Preto
    c_muted = colors.HexColor("#475569")  # Texto Secundário

    style_title = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=c_primary,
    )

    style_subtitle = ParagraphStyle(
        "DocSubtitle",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=c_muted,
    )

    style_meta = ParagraphStyle(
        "DocMeta",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#0284C7"),
    )

    style_h1 = ParagraphStyle(
        "SectionH1",
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14.5,
        textColor=c_primary,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )

    style_h2 = ParagraphStyle(
        "SectionH2",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12.5,
        textColor=c_secondary,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True,
    )

    style_body = ParagraphStyle(
        "BodyDark",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_dark,
        spaceAfter=4,
    )

    style_bullet = ParagraphStyle(
        "BulletDark",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_dark,
        leftIndent=11,
        firstLineIndent=-7,
        spaceAfter=2.5,
    )

    style_th = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
    )

    style_td = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.5,
        textColor=c_dark,
    )

    style_td_bold = ParagraphStyle(
        "TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=9.5,
        textColor=c_primary,
    )

    story = []

    # =========================================================================
    # PÁGINA 1: O PROJETO SÓCIO DIGITAL (CONTEXTO, PROBLEMA E REQUISITOS)
    # =========================================================================
    header_data = [
        [Paragraph("SÓCIO DIGITAL: COPILOTO DE GESTÃO FISCAL", style_title)],
        [
            Paragraph(
                "Relatório Consolidado de Arquitetura, Inteligência de RAG Tributário e Práticas de DevOps/MLOps",
                style_subtitle,
            )
        ],
        [
            Paragraph(
                "<b>Programa:</b> Residência em Inteligência Artificial (RES-IA) | <b>Desafio:</b> Challenge 2 — Grupo 08<br/>"
                "<b>Integrantes:</b> Clara, Ingrid, Jhessica, Lucas, Nasser &nbsp;|&nbsp; <b>Data:</b> Novembro / 2026",
                style_meta,
            )
        ],
    ]
    t_header = Table(header_data, colWidths=[519])
    t_header.setStyle(
        TableStyle(
            [
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(t_header)
    story.append(
        HRFlowable(width="100%", thickness=1.2, color=c_primary, spaceBefore=3, spaceAfter=6)
    )

    story.append(Paragraph("1. O Projeto Sócio Digital: Contexto e Fundamentos", style_h1))
    story.append(
        Paragraph(
            "O <b>Sócio Digital</b> é uma solução de Inteligência Artificial voltada para microempreendedores individuais (MEIs) "
            "e proprietários de microempresas (MEs e EPPs). No Brasil, pequenos negócios somam mais de <b>24 milhões de empresas ativas</b> "
            "(95% do total nacional). A complexidade normativa, a dispersão de portais públicos e a falta de formação contábil básica "
            "geram dependência cega do contador, ansiedade financeira e risco elevado de multas e desenquadramentos involuntários.",
            style_body,
        )
    )

    eq_text = (
        '<i>"Como a inteligência artificial generativa integrada a técnicas de recuperação factual (RAG) '
        "pode simplificar a gestão de obrigações contábeis e tributárias de pequenos empreendedores, promovendo "
        'maior autonomia e reduzindo a sobrecarga administrativa que afeta sua qualidade de vida?"</i>'
    )
    story.append(
        create_callout(
            eq_text,
            title="Essential Question (Pergunta Central da Equipe)",
            border_color="#1E3A8A",
            bg_color="#F1F5F9",
            width=519,
        )
    )
    story.append(Spacer(1, 4))

    story.append(Paragraph("Diferencial Central da Solução", style_h2))
    story.append(
        Paragraph(
            "O diferencial do Sócio Digital é superar chatbots generalistas e conversas descartáveis: diante de uma dúvida relatada, "
            "o sistema extrai o contexto da empresa, consulta a base normativa por RAG, aciona o motor determinístico para cálculo exato "
            "e devolve um <b>plano de ação estruturado de no máximo 3 etapas concretas</b>, vinculando prazos, documentos e permitindo "
            "o acompanhamento do semáforo fiscal no painel do usuário.",
            style_body,
        )
    )

    story.append(Paragraph("Fronteiras Éticas e Delimitação Legal", style_h2))
    story.append(
        Paragraph(
            "O assistente opera como copiloto educativo e organizador. <b>Não substitui as atribuições privativas de contadores habilitados (CRC)</b> "
            "nem comprova regularidade perante o Fisco sem consulta oficial. O sistema incorpora abstenção ativa em matérias de incerteza "
            "ou litígio, encaminhando formalmente o usuário para validação especializada com seu contador.",
            style_body,
        )
    )

    story.append(Paragraph("Matriz de Requisitos Centrais do Sistema (MVP)", style_h2))
    req_data = [
        [
            Paragraph("ID", style_th),
            Paragraph("Requisito Funcional / Não Funcional", style_th),
            Paragraph("Descrição Técnica & Critério no MVP", style_th),
            Paragraph("Prioridade", style_th),
        ],
        [
            Paragraph("RF01", style_td_bold),
            Paragraph("Cadastro do Contexto", style_td),
            Paragraph(
                "Registro de porte (MEI/ME), CNAE, regime tributário e localização.", style_td
            ),
            Paragraph("Alta", style_td),
        ],
        [
            Paragraph("RF02/03", style_td_bold),
            Paragraph("Assistente & RAG Factual", style_td),
            Paragraph(
                "Interface conversacional com recuperação estrita de fontes consolidadas (LC 123, CGSN).",
                style_td,
            ),
            Paragraph("Alta", style_td),
        ],
        [
            Paragraph("RF06/07", style_td_bold),
            Paragraph("Painel & Planos de Ação", style_td),
            Paragraph(
                "Dashboard com semáforo de status e geração de roteiros de ação em até 3 etapas.",
                style_td,
            ),
            Paragraph("Alta", style_td),
        ],
        [
            Paragraph("RNF04", style_td_bold),
            Paragraph("Tratamento de Incertezas", style_td),
            Paragraph(
                "Abstenção proativa e encaminhamento ao CRC se a base normativa for insuficiente.",
                style_td,
            ),
            Paragraph("Crítica", style_td),
        ],
        [
            Paragraph("RNF05", style_td_bold),
            Paragraph("Citações Verificáveis", style_td),
            Paragraph(
                "Citação explícita do artigo, parágrafo e data de vigência da lei em toda orientação.",
                style_td,
            ),
            Paragraph("Alta", style_td),
        ],
        [
            Paragraph("RNF08", style_td_bold),
            Paragraph("Latência Controlada", style_td),
            Paragraph(
                "Tempo de resposta inferior a 3s no motor determinístico e < 10s no pipeline RAG.",
                style_td,
            ),
            Paragraph("Média", style_td),
        ],
    ]
    t_req = Table(req_data, colWidths=[42, 120, 297, 60])
    t_req.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_req)

    # QUEBRA PARA PÁGINA 2
    story.append(PageBreak())

    # =========================================================================
    # PÁGINA 2: ARQUITETURA DO RAG TRIBUTÁRIO (CIÊNCIA DE DADOS)
    # =========================================================================
    story.append(
        Paragraph("2. Inteligência e Arquitetura do RAG Tributário (Ciência de Dados)", style_h1)
    )
    story.append(
        Paragraph(
            "A frente de Ciência de Dados (liderada por Jhessica) estruturou uma arquitetura especializada de RAG "
            "para solucionar a complexidade jurídica brasileira. O 'chunking ingênuo' por quantidade cega de caracteres quebra "
            "a hierarquia legal (artigos, parágrafos e incisos), separando regras gerais de suas condições de exceção. "
            "Para garantir zero alucinações normativas, o sistema fundamenta-se em quatro pilares:",
            style_body,
        )
    )

    story.append(Paragraph("Os Quatro Pilares da Solução de RAG", style_h2))

    story.append(
        Paragraph(
            "<b>1. Chunking Hierárquico Jurídico (<code>LegalHierarchicalChunker</code>):</b> "
            "Parser ciente da estrutura normativa brasileira (`ARTICLE_REGEX`, `PARAGRAPH_REGEX`). "
            "Preserva a integridade do Artigo e seus Parágrafos. Aplica <b>Context Injection</b> gerando cabeçalhos "
            "como <code>[FONTE: LC 123 | ARTIGO: Art. 18 | PARÁGRAFO: § 5º-J | TEMA: Fator R]</code> antes do embedding. "
            "Em artigos extensos, subdivide em parágrafos preservando o <i>Caput</i> como âncora fixa.",
            style_bullet,
        )
    )

    story.append(
        Paragraph(
            "<b>2. Banco Vetorial e Busca Híbrida (<code>LegalVectorStore</code>):</b> "
            "Indexação semântica densa com <code>sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2</code> "
            "(384 dimensões) com fallback em TF-IDF/Python puro. Persistência em SQLite com vetores serializados. "
            "A recuperação calcula o score: <b>0.70 × Similaridade Cosseno + 0.30 × Correspondência Léxica Exata</b>, "
            "com filtros temáticos particionados por tags fiscais (`mei`, `fator_r`, `desenquadramento`, etc.).",
            style_bullet,
        )
    )

    story.append(
        Paragraph(
            "<b>3. Extrator de Entidades Fiscais e NER (<code>TaxEntityExtractor</code>):</b> "
            "Identificação em milissegundos de CNPJs, CNAEs, regimes, anexos e valores monetários "
            "(distinguindo faturamento anual RBT12, faturamento mensal, folha 12m e débitos tributários). "
            "Aplica <b>Query Expansion</b>, traduzindo perguntas em linguagem coloquial para a terminologia oficial.",
            style_bullet,
        )
    )

    story.append(
        Paragraph(
            "<b>4. Desacoplamento Determinístico vs Generativo (Garantia Antialucinação):</b> "
            "Separação arquitetural estrita (Clara e Nasser): <b>o LLM nunca realiza cálculos matemáticos de impostos</b>. "
            "O extrator fornece dados para o motor em Python (<code>FiscalCalculator</code> do Lucas), que calcula a "
            "alíquota efetiva (Art. 18 da LC 123/2006) e Fator R. O RAG recupera a lei. O LLM apenas redige a explicação.",
            style_bullet,
        )
    )

    story.append(Spacer(1, 4))
    story.append(Paragraph("Corpora Oficiais Ingeridos e Indexados no Banco Vetorial", style_h2))
    corp_data = [
        [
            Paragraph("Documento Fonte", style_th),
            Paragraph("Esfera & Órgão", style_th),
            Paragraph("Conteúdo Normativo Mapeado", style_th),
            Paragraph("Escopo Indexado", style_th),
        ],
        [
            Paragraph("Lei Complementar nº 123/2006", style_td_bold),
            Paragraph("Presidência da República", style_td),
            Paragraph("Estatuto da MPE, Anexos I a V, Fator R, sublimites e MEI.", style_td),
            Paragraph("Artigos 18, 18-A e §§", style_td),
        ],
        [
            Paragraph("Resolução CGSN nº 140/2018", style_td_bold),
            Paragraph("Comitê Gestor Simples", style_td),
            Paragraph("Regulamento operacional, declarações (DASN-SIMEI) e multas.", style_td),
            Paragraph("Artigos 106 e segs.", style_td),
        ],
        [
            Paragraph("Manual de Regularização Fiscal", style_td_bold),
            Paragraph("Receita Federal / PGFN", style_td),
            Paragraph("Emissão de certidões (CND/CPEN), parcelamentos e cobrança.", style_td),
            Paragraph("Artigos 1º a 15", style_td),
        ],
        [
            Paragraph("Catálogo Oficial de CNAEs & Anexos", style_td_bold),
            Paragraph("IBGE / Comitê Simples", style_td),
            Paragraph("Tabelas completas de alíquotas nominais e Fator R por CNAE.", style_td),
            Paragraph("JSON estruturado / FTS5", style_td),
        ],
    ]
    t_corp = Table(corp_data, colWidths=[130, 95, 214, 80])
    t_corp.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_secondary),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_corp)

    story.append(Spacer(1, 4))
    story.append(
        Paragraph("Validação Empírica dos Casos Canônicos de Teste (100% de Sucesso)", style_h2)
    )
    cases_data = [
        [
            Paragraph("Cenário de Teste", style_th),
            Paragraph("Pergunta do Usuário", style_th),
            Paragraph("Artigo Legal Recuperado (Top-1)", style_th),
            Paragraph("Status", style_th),
        ],
        [
            Paragraph("1. Limite e Excesso MEI", style_td_bold),
            Paragraph(
                "Faturei R$ 105 mil no MEI (> 20% de excesso). Serei desenquadrado?", style_td
            ),
            Paragraph(
                "LC 123/2006, Art. 18-A, § 7º (Desenquadramento retroativo a 1º jan)", style_td
            ),
            Paragraph("<b>100% OK</b>", style_td_bold),
        ],
        [
            Paragraph("2. Fator R e Anexos", style_td_bold),
            Paragraph(
                "CNAE 6201-5/01 faturou R$ 300k com folha de R$ 90k (30%). Qual anexo?", style_td
            ),
            Paragraph(
                "LC 123/2006, Art. 18, §§ 5º-J e 5º-M (Fator R >= 28% -> Anexo III)", style_td
            ),
            Paragraph("<b>100% OK</b>", style_td_bold),
        ],
        [
            Paragraph("3. Obrigação Acessória", style_td_bold),
            Paragraph("Qual a data limite da DASN-SIMEI e valor da multa por atraso?", style_td),
            Paragraph(
                "Res. CGSN 140/2018, Art. 106 (Prazo 31 de maio e multa mín. R$ 50)", style_td
            ),
            Paragraph("<b>100% OK</b>", style_td_bold),
        ],
        [
            Paragraph("4. Regularização e CPEN", style_td_bold),
            Paragraph(
                "Recebi notificação de dívida de R$ 15 mil. O parcelamento em 60x libera CPEN?",
                style_td,
            ),
            Paragraph(
                "Manual Receita Federal, Art. 1º (Parcelamento ativo emite certidão positiva)",
                style_td,
            ),
            Paragraph("<b>100% OK</b>", style_td_bold),
        ],
    ]
    t_cases = Table(cases_data, colWidths=[105, 160, 194, 60])
    t_cases.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_cases)

    # QUEBRA PARA PÁGINA 3
    story.append(PageBreak())

    # =========================================================================
    # PÁGINA 3: PRÁTICAS DE DEVOPS E MLOPS (ENGENHARIA DE PLATAFORMA)
    # =========================================================================
    story.append(Paragraph("3. Práticas de DevOps e MLOps: Esteira e Governança", style_h1))
    story.append(
        Paragraph(
            "A frente de Ops (liderada por Ingrid) estabeleceu a infraestrutura automatizada de Integração Contínua (CI), "
            "governança de dados normativos e esteiras reproduzíveis via containers, garantindo rastreabilidade total "
            "entre versões de código, modelos de RAG e tabelas fiscais.",
            style_body,
        )
    )

    story.append(Paragraph("Stack Tecnológica Integrada de DevOps e MLOps", style_h2))
    stack_data = [
        [
            Paragraph("Componente", style_th),
            Paragraph("Tecnologia Adotada", style_th),
            Paragraph("Propósito e Escopo de Operação", style_th),
        ],
        [
            Paragraph("Controle de Versão", style_td_bold),
            Paragraph("Git & GitHub", style_td),
            Paragraph(
                "Repositório central `ingrdsoares/RES-IA-Challenge-2` com fluxo estrito de PRs.",
                style_td,
            ),
        ],
        [
            Paragraph("Portal Docs-as-Code", style_td_bold),
            Paragraph("Docsify / Pages", style_td),
            Paragraph(
                "Documentação viva renderizada via CDN e deployada pelo GitHub Actions (`pages.yml`).",
                style_td,
            ),
        ],
        [
            Paragraph("Integração Contínua (CI)", style_td_bold),
            Paragraph("GitHub Actions", style_td),
            Paragraph(
                "Pipeline multi-job (`ci.yml`) disparada a cada push/PR para linters, testes e builds.",
                style_td,
            ),
        ],
        [
            Paragraph("Versionamento de Dados", style_td_bold),
            Paragraph("DVC (Data Version Control)", style_td),
            Paragraph(
                "Rastreamento de corpora fiscais e bancos SQLite com integridade por SHA-256.",
                style_td,
            ),
        ],
        [
            Paragraph("Padronização de Código", style_td_bold),
            Paragraph("Ruff & Pytest", style_td),
            Paragraph(
                "Linter e formatador de alta performance configurados no `pyproject.toml`.",
                style_td,
            ),
        ],
        [
            Paragraph("Conteinerização", style_td_bold),
            Paragraph("Docker (FastAPI)", style_td),
            Paragraph(
                "Imagem leve e segura (`python:3.12-slim`) em `api/Dockerfile` para os microsserviços.",
                style_td,
            ),
        ],
    ]
    t_stack = Table(stack_data, colWidths=[105, 115, 299])
    t_stack.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_stack)

    story.append(Spacer(1, 4))
    story.append(Paragraph("Esteira de Integração Contínua (Workflow GitHub Actions)", style_h2))
    story.append(
        Paragraph(
            "A esteira automatizada em <code>.github/workflows/ci.yml</code> opera como o primeiro portão de qualidade do projeto. "
            "A cada alteração enviada ao repositório, quatro validações críticas são executadas em paralelo:",
            style_body,
        )
    )
    story.append(
        Paragraph(
            "• <b>Job `lint` (Qualidade de Código):</b> Checagem de tipagem e formatação via Ruff em menos de 2 segundos.",
            style_bullet,
        )
    )
    story.append(
        Paragraph(
            "• <b>Job `test` (Testes Unitários e Fiscais):</b> Executa o Pytest para validar as rotas da API e os motores de cálculo.",
            style_bullet,
        )
    )
    story.append(
        Paragraph(
            "• <b>Job `dvc-validation` (Integridade de Dados):</b> Executa `dvc doctor` e checa se há drift de ponteiros normativos.",
            style_bullet,
        )
    )
    story.append(
        Paragraph(
            "• <b>Job `docker-smoke-test` (Build de Imagem):</b> Executa o build da imagem Docker da API para garantir deployabilidade.",
            style_bullet,
        )
    )

    story.append(Spacer(1, 4))
    story.append(Paragraph("Governança e Versionamento de Dados com DVC", style_h2))
    story.append(
        Paragraph(
            "Seguindo a política de segregação de artefatos volumosos, o DVC separa o ciclo de vida do código das bases tributárias: "
            "<b>`data/raw/`</b> guarda arquivos brutos auditáveis e imutáveis, enquanto <b>`data/processed/`</b> recebe o banco relacional "
            "e os índices vetoriais. Cada versão de dados gera um arquivo ponte de metadados (`.dvc`) com hash SHA-256, permitindo "
            "que qualquer membro da equipe sincronize exatamente a mesma base legal com <code>dvc pull</code>.",
            style_body,
        )
    )

    story.append(Spacer(1, 4))
    dvc_callout = (
        "<b>Padrão de Governança de Corpora Fiscais (DVC):</b><br/>"
        "• Arquivos de dados binários (*.db) e índices vetoriais não são comitados diretamente no Git.<br/>"
        "• Cada atualização em tabelas do Simples ou manuais fiscais gera um commit no Git contendo apenas os ponteiros `.dvc`.<br/>"
        "• Armazenamento configurado com suporte a remotes locais compartilhados e compatibilidade nativa com buckets S3/GCP."
    )
    story.append(
        create_callout(
            dvc_callout,
            title="Diretriz de MLOps: Rastreabilidade Estrita de Dados",
            border_color="#0284C7",
            bg_color="#F0F9FF",
            width=519,
        )
    )

    # QUEBRA PARA PÁGINA 4
    story.append(PageBreak())

    # =========================================================================
    # PÁGINA 4: MATRIZ DE RESPONSABILIDADES, GOVERNANÇA E ROADMAP
    # =========================================================================
    story.append(Paragraph("4. Governança da Equipe e Roadmap de Entrega", style_h1))
    story.append(
        Paragraph(
            "O projeto organiza-se em um modelo colaborativo multidisciplinar com responsabilidades claramente distribuídas "
            "entre Engenharia de Dados, Ciência de Dados, Arquitetura de Software e DevOps/MLOps:",
            style_body,
        )
    )

    story.append(Paragraph("Matriz de Atribuições da Equipe (Grupo 08)", style_h2))
    team_data = [
        [
            Paragraph("Integrante", style_th),
            Paragraph("Frente de Atuação", style_th),
            Paragraph("Entregas Concluídas", style_th),
            Paragraph("Próximos Passos Imediatos", style_th),
        ],
        [
            Paragraph("Lucas", style_td_bold),
            Paragraph("Engenharia de Dados & Dev", style_td),
            Paragraph("Motor fiscal (`calculator.py`), base CNAEs e tabelas LC 123.", style_td),
            Paragraph("Conectar endpoints da API FastAPI ao motor fiscal.", style_td),
        ],
        [
            Paragraph("Jhessica", style_td_bold),
            Paragraph("Ciência de Dados", style_td),
            Paragraph("Chunking hierárquico, VectorStore SQLite e NER Fiscal.", style_td),
            Paragraph("Engenharia de prompt final e métricas Ragas.", style_td),
        ],
        [
            Paragraph("Clara e Nasser", style_td_bold),
            Paragraph("Arquitetura de Soluções", style_td),
            Paragraph("Topologia desacoplada, segurança/LGPD e fronteira CRC.", style_td),
            Paragraph("Contratos de OpenAPI e modelo multi-tenant.", style_td),
        ],
        [
            Paragraph("Ingrid", style_td_bold),
            Paragraph("Ops (DevOps & MLOps)", style_td),
            Paragraph("GitHub Actions (CI/Pages), DVC e governança de repositório.", style_td),
            Paragraph("Merge da branch de RAG e deploy contínuo (CD).", style_td),
        ],
    ]
    t_team = Table(team_data, colWidths=[70, 115, 174, 160])
    t_team.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_team)

    story.append(Spacer(1, 6))
    story.append(Paragraph("Critérios de Avaliação e Indicadores de Sucesso (Go/No-Go)", style_h2))
    story.append(
        Paragraph(
            "A passagem para a fase de inferência em produção obedece a métricas objetivas de qualidade:",
            style_body,
        )
    )
    story.append(
        Paragraph(
            "• <b>Acurácia e Corretude Normativa:</b> Meta de <b>pelo menos 85% de exatidão global e 0% de erros críticos</b> em cenários de enquadramento tributário auditados por especialistas contábeis.",
            style_bullet,
        )
    )
    story.append(
        Paragraph(
            "• <b>Ancoragem Legal (Faithfulness):</b> Meta de <b>pelo menos 95% das orientações com citações legais diretas</b> e verificáveis nos diplomas da LC 123/2006 ou Resoluções do CGSN.",
            style_bullet,
        )
    )
    story.append(
        Paragraph(
            "• <b>Compreensão Prática:</b> Pelo menos 80% dos usuários capazes de executar o plano de 3 passos sem dúvidas adicionais.",
            style_bullet,
        )
    )
    story.append(
        Paragraph(
            "• <b>Desempenho de Latência:</b> Inferência na API em menos de 3 segundos para cálculos matemáticos e menos de 10 segundos para respostas completas ancoradas em RAG.",
            style_bullet,
        )
    )

    story.append(Spacer(1, 6))
    roadmap_callout = (
        "<b>Roteiro de Fechamento da Fase 2 e Transição para a Fase 3:</b><br/>"
        "1. <b>Merge Oficial da Branch RAG:</b> Realizar a integração de `origin/feat/rag-pipeline-ingestao` na branch `main`.<br/>"
        "2. <b>Rastreamento Efetivo DVC:</b> Executar `dvc add data/raw` e registrar os arquivos de manifesto SHA-256 no Git.<br/>"
        "3. <b>Exposição dos Endpoints da API:</b> Implementar rotas `/api/v1/consultar-duvida` e `/api/v1/simular-simples`.<br/>"
        "4. <b>Pipeline de Validação Contínua de RAG:</b> Integrar os testes de recuperação factual ao CI do GitHub Actions.<br/>"
        "5. <b>Ambiente de Homologação:</b> Configurar deploy automático da API conteinerizada em ambiente de nuvem."
    )
    story.append(
        create_callout(
            roadmap_callout,
            title="Checklist de Execução para a Próxima Entrega Oficial",
            border_color="#1E3A8A",
            bg_color="#F1F5F9",
            width=519,
        )
    )

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[Sucesso] PDF gerado em: {filename}")


if __name__ == "__main__":
    out_pdf = "docs/entrega/relatorio-socio-digital-rag-mlops.pdf"
    if len(sys.argv) > 1:
        out_pdf = sys.argv[1]
    build_pdf(out_pdf)
