"""
Gerador de PDF Executivo — Sócio Digital: Mapeamento de Entregas da Equipe (Grupo 08)
Produz um documento PDF elegante, profissional e sem dependências externas.
"""

from pathlib import Path


class PDFCanvas:
    def __init__(self, filename):
        self.filename = filename
        self.pages = []
        self.current_page_ops = []
        self.width = 595.28  # A4 width in pt
        self.height = 841.89  # A4 height in pt

    def new_page(self):
        if self.current_page_ops:
            self.pages.append(self.current_page_ops)
            self.current_page_ops = []

    def save(self):
        if self.current_page_ops:
            self.pages.append(self.current_page_ops)
            self.current_page_ops = []

        total_pages = len(self.pages)

        catalog_id = 1
        pages_id = 2
        font_reg_id = 3
        font_bold_id = 4
        font_italic_id = 5

        page_obj_ids = []
        content_obj_ids = []
        current_id = 6
        for p in range(total_pages):
            page_obj_ids.append(current_id)
            content_obj_ids.append(current_id + 1)
            current_id += 2

        obj_catalog = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
        kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
        obj_pages = f"<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>"
        obj_font_reg = (
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        )
        obj_font_bold = (
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        )
        obj_font_italic = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"

        objs = [
            obj_catalog,
            obj_pages,
            obj_font_reg,
            obj_font_bold,
            obj_font_italic,
        ]

        for p_idx in range(total_pages):
            c_obj_id = content_obj_ids[p_idx]

            page_ops = list(self.pages[p_idx])

            # Running footer line and text
            page_ops.append("q 0.85 0.88 0.92 RG 0.75 w 45 40 m 550.28 40 l S Q")
            page_ops.append(
                "BT /F1 8 Tf 0.45 0.52 0.60 rg 45 28 Td (S\xf3cio Digital \x97"
                " Relat\xf3rio de Entregas da Equipe | RES-IA Challenge 2"
                " \x97 Grupo 08) Tj ET"
            )
            p_num_str = f"P\xe1gina {p_idx + 1} de {total_pages}"
            page_ops.append(f"BT /F2 8 Tf 0.45 0.52 0.60 rg 495 28 Td ({p_num_str}) Tj ET")

            stream_content = "\n".join(page_ops)
            stream_bytes = stream_content.encode("latin1")
            stream_len = len(stream_bytes)

            obj_page = (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0"
                f" {self.width:.2f} {self.height:.2f}] /Contents {c_obj_id} 0"
                f" R /Resources << /Font << /F1 {font_reg_id} 0 R /F2"
                f" {font_bold_id} 0 R /F3 {font_italic_id} 0 R >> >> >>"
            )
            obj_stream = f"<< /Length {stream_len} >>\nstream\n{stream_content}\nendstream"

            objs.append(obj_page)
            objs.append(obj_stream)

        with open(self.filename, "wb") as f:
            f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            offsets = []
            for i, obj in enumerate(objs, 1):
                offsets.append(f.tell())
                f.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin1"))

            xref_offset = f.tell()
            f.write(b"xref\n")
            f.write(f"0 {len(objs) + 1}\n".encode("latin1"))
            f.write(b"0000000000 65535 f \n")
            for off in offsets:
                f.write(f"{off:010d} 00000 n \n".encode("latin1"))

            f.write(b"trailer\n")
            f.write(f"<< /Size {len(objs) + 1} /Root {catalog_id} 0 R >>\n".encode("latin1"))
            f.write(b"startxref\n")
            f.write(f"{xref_offset}\n%%EOF\n".encode("latin1"))


def escape_pdf_text(s):
    encoded = s.encode("cp1252", errors="replace")
    out = bytearray()
    for b in encoded:
        if b == ord("\\"):
            out.extend(b"\\\\")
        elif b == ord("("):
            out.extend(b"\\(")
        elif b == ord(")"):
            out.extend(b"\\)")
        else:
            out.append(b)
    return out.decode("latin1")


def wrap_text(text, max_chars):
    words = text.split(" ")
    lines = []
    cur = []
    for w in words:
        test = " ".join(cur + [w])
        if len(test) > max_chars:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


class DocumentBuilder:
    def __init__(self, filename):
        self.canvas = PDFCanvas(filename)
        self.canvas.new_page()
        self.y = 800
        self.left = 45
        self.right = 550.28
        self.usable_width = self.right - self.left

    def check_space(self, required_height):
        if self.y - required_height < 60:
            self.canvas.new_page()
            self.y = 790
            self.draw_page_header()

    def draw_page_header(self):
        ops = self.canvas.current_page_ops
        ops.append("q 0.08 0.16 0.32 rg 45 808 505.28 2 re f Q")
        ops.append(
            "BT /F2 8 Tf 0.30 0.38 0.48 rg 45 814 Td (S\xd3CIO DIGITAL \x97"
            " MAPEAMENTO DE ENTREGAS DA EQUIPE) Tj ET"
        )
        ops.append(
            "BT /F1 8 Tf 0.45 0.52 0.60 rg 440 814 Td (RES-IA | Challenge 2 \x97 Grupo 08) Tj ET"
        )
        self.y = 788

    def draw_cover_banner(self):
        ops = self.canvas.current_page_ops
        ops.append("q 0.06 0.12 0.28 rg 45 745 505.28 65 re f Q")
        ops.append("q 0.85 0.65 0.13 rg 45 807 505.28 3 re f Q")

        ops.append(
            "BT /F2 14.5 Tf 1 1 1 rg 60 782 Td (S\xd3CIO DIGITAL: RELAT\xd3RIO"
            " DE ENTREGAS DA EQUIPE) Tj ET"
        )
        ops.append(
            "BT /F1 9 Tf 0.85 0.90 0.98 rg 60 766 Td (RES-IA Challenge 2 \x97"
            " Grupo 08 | Clara, Ingrid, Jhessica, Lucas, Nasser) Tj ET"
        )
        ops.append(
            "BT /F2 8.5 Tf 0.95 0.75 0.25 rg 60 752 Td (MAPA T\xc9CNICO DE"
            " ATUA\xc7\xc3O: C\xd3DIGO, ARQUITETURA, DADOS E MLOPS) Tj ET"
        )
        self.y = 726

    def draw_section_title(self, title, subtitle=None, badge=None):
        self.check_space(42)
        ops = self.canvas.current_page_ops
        ops.append(f"q 0.10 0.28 0.65 rg 45 {self.y - 13} 4 15 re f Q")

        escaped_title = escape_pdf_text(title)
        ops.append(f"BT /F2 11 Tf 0.08 0.14 0.25 rg 55 {self.y - 11} Td ({escaped_title}) Tj ET")

        if badge:
            e_badge = escape_pdf_text(badge)
            ops.append(
                f"q 0.92 0.95 1.0 rg 0.70 0.80 0.95 RG 0.5 w 420 {self.y - 14} 130 14 re B Q"
            )
            ops.append(f"BT /F2 7.5 Tf 0.10 0.30 0.70 rg 428 {self.y - 10} Td ({e_badge}) Tj ET")

        self.y -= 17

        if subtitle:
            escaped_sub = escape_pdf_text(subtitle)
            ops.append(f"BT /F3 8.5 Tf 0.40 0.45 0.55 rg 55 {self.y - 7} Td ({escaped_sub}) Tj ET")
            self.y -= 13
        self.y -= 3

    def draw_card(self, title, items, bg_rgb=(0.96, 0.98, 1.0), border_rgb=(0.75, 0.85, 0.95)):
        max_chars = 95
        rendered_lines = []
        for prefix, text, is_bullet in items:
            if not prefix and not text:
                rendered_lines.append(("", "", False, True))
                continue

            prefix_len = len(prefix)
            avail_chars = max_chars - (prefix_len if prefix else 0) - (4 if is_bullet else 0)
            sub_lines = wrap_text(text, avail_chars)
            if not sub_lines:
                rendered_lines.append((prefix, "", is_bullet, False))
            else:
                rendered_lines.append((prefix, sub_lines[0], is_bullet, False))
                for sl in sub_lines[1:]:
                    rendered_lines.append(("", sl, False, False))

        header_h = 20 if title else 6
        body_h = len(rendered_lines) * 12 + 8
        total_h = header_h + body_h

        self.check_space(total_h + 8)
        ops = self.canvas.current_page_ops

        r_bg, g_bg, b_bg = bg_rgb
        r_bd, g_bd, b_bd = border_rgb
        card_y = self.y - total_h
        ops.append(
            f"q {r_bg:.2f} {g_bg:.2f} {b_bg:.2f} rg {r_bd:.2f} {g_bd:.2f} {b_bd:.2f} RG 0.8 w 45 {card_y} 505.28 {total_h} re B Q"
        )

        cur_text_y = self.y - 14
        if title:
            escaped_title = escape_pdf_text(title)
            ops.append(
                f"BT /F2 9.5 Tf 0.08 0.18 0.40 rg 57 {cur_text_y} Td ({escaped_title}) Tj ET"
            )
            cur_text_y -= 13

        for prefix, line_text, is_bullet, is_blank in rendered_lines:
            if is_blank:
                cur_text_y -= 6
                continue

            indent_x = 57
            if is_bullet:
                ops.append(f"q 0.20 0.40 0.70 rg 58 {cur_text_y + 2} 3 3 re f Q")
                indent_x = 66
            elif not prefix and indent_x == 57:
                indent_x = 66 if any(it[2] for it in items) else 57

            if prefix:
                e_p = escape_pdf_text(prefix)
                e_t = escape_pdf_text(" " + line_text if line_text else "")
                ops.append(
                    f"BT /F2 8.5 Tf 0.10 0.15 0.25 rg {indent_x} {cur_text_y} Td ({e_p}) Tj /F1 8.5 Tf 0.20 0.25 0.35 rg ({e_t}) Tj ET"
                )
            else:
                e_t = escape_pdf_text(line_text)
                ops.append(
                    f"BT /F1 8.5 Tf 0.20 0.25 0.35 rg {indent_x} {cur_text_y} Td ({e_t}) Tj ET"
                )

            cur_text_y -= 12

        self.y = card_y - 8

    def draw_paragraph(self, text, font="F1", size=8.8, leading=12, color=(0.15, 0.20, 0.28)):
        max_chars = int(self.usable_width / (size * 0.52))
        lines = wrap_text(text, max_chars)

        req_h = len(lines) * leading
        self.check_space(req_h)

        ops = self.canvas.current_page_ops
        r, g, b = color
        for line in lines:
            escaped = escape_pdf_text(line)
            ops.append(
                f"BT /{font} {size} Tf {r:.2f} {g:.2f} {b:.2f} rg {self.left} {self.y - size} Td ({escaped}) Tj ET"
            )
            self.y -= leading
        self.y -= 3

    def draw_bullet(self, bold_prefix, text, size=8.5, leading=11.5):
        max_chars = int((self.usable_width - 18) / (size * 0.52))
        sub_lines = wrap_text(text, max_chars - len(bold_prefix) - 2)

        req_h = (1 + len(sub_lines) - 1) * leading
        self.check_space(req_h + 4)

        ops = self.canvas.current_page_ops
        bullet_y = self.y - size + 2
        ops.append(f"q 0.15 0.35 0.70 rg {self.left + 2} {bullet_y} 3.5 3.5 re f Q")

        e_bp = escape_pdf_text(bold_prefix)
        first_content = sub_lines[0] if sub_lines else ""
        e_rem = escape_pdf_text(" " + first_content if first_content else "")
        ops.append(
            f"BT /F2 {size} Tf 0.10 0.15 0.25 rg {self.left + 12} {self.y - size} Td ({e_bp}) Tj /F1 {size} Tf 0.20 0.25 0.35 rg ({e_rem}) Tj ET"
        )
        self.y -= leading

        for sub_line in sub_lines[1:]:
            e_l = escape_pdf_text(sub_line)
            ops.append(
                f"BT /F1 {size} Tf 0.20 0.25 0.35 rg {self.left + 12} {self.y - size} Td ({e_l}) Tj ET"
            )
            self.y -= leading
        self.y -= 2

    def draw_table(self, headers, rows, col_widths):
        table_rows_data = []
        total_h = 20
        for r_idx, r_data in enumerate(rows):
            max_lines = 1
            wrapped_cells = []
            for c_idx, (val, w) in enumerate(zip(r_data, col_widths)):
                approx_chars = int((w - 8) / 4.4)
                w_lines = wrap_text(val, approx_chars)
                if len(w_lines) > max_lines:
                    max_lines = len(w_lines)
                wrapped_cells.append(w_lines)
            row_h = max_lines * 10 + 6
            table_rows_data.append((wrapped_cells, row_h))
            total_h += row_h

        self.check_space(total_h + 8)
        ops = self.canvas.current_page_ops

        start_y = self.y
        table_y = start_y - total_h

        # Header background
        ops.append(f"q 0.10 0.18 0.35 rg 45 {start_y - 18} 505.28 18 re f Q")

        # Header text
        cur_x = 45
        for idx, (h, w) in enumerate(zip(headers, col_widths)):
            eh = escape_pdf_text(h)
            ops.append(f"BT /F2 8 Tf 1 1 1 rg {cur_x + 5} {start_y - 12.5} Td ({eh}) Tj ET")
            cur_x += w

        # Draw rows
        row_y = start_y - 18
        for r_idx, (wrapped_cells, row_h) in enumerate(table_rows_data):
            bg = "0.96 0.97 1.0" if r_idx % 2 == 0 else "1 1 1"
            ops.append(f"q {bg} rg 45 {row_y - row_h} 505.28 {row_h} re f Q")
            ops.append(
                f"q 0.85 0.88 0.94 RG 0.5 w 45 {row_y - row_h} m 550.28 {row_y - row_h} l S Q"
            )

            cur_x = 45
            for c_idx, (lines, w) in enumerate(zip(wrapped_cells, col_widths)):
                font = "/F2" if c_idx == 0 else "/F1"
                color = "0.08 0.14 0.28 rg" if c_idx == 0 else "0.18 0.22 0.30 rg"
                cell_y = row_y - 9.5
                for text_line in lines:
                    el = escape_pdf_text(text_line)
                    ops.append(f"BT {font} 7.5 Tf {color} {cur_x + 5} {cell_y} Td ({el}) Tj ET")
                    cell_y -= 9.5
                cur_x += w
            row_y -= row_h

        # Outer border
        ops.append(f"q 0.70 0.76 0.88 RG 0.75 w 45 {table_y} 505.28 {total_h} re S Q")
        self.y = table_y - 10


def generate_document():
    pdf_path = Path(
        "/Users/aluno2/RES-IA-Challenge-2/docs/entrega/status-entregas-equipe-grupo-08.pdf"
    )
    doc = DocumentBuilder(str(pdf_path))

    # ========================================================
    # PÁGINA 1: VISÃO GERAL & CIÊNCIA DE DADOS (JHESSICA)
    # ========================================================
    doc.draw_cover_banner()

    doc.draw_card(
        "Quadro Sinóptico de Atuação do Grupo 08",
        [
            (
                "Jhessica (Ciência de Dados):",
                "RAG factual, Chunking hierárquico, NER fiscal, Guardrails anti-alucinação e RAGService.",
                True,
            ),
            (
                "Lucas (Engenharia de Dados & Dev):",
                "Ingestão estruturada de CNAEs/LC 123, Motor determinístico em Python e base FastAPI.",
                True,
            ),
            (
                "Clara e Nasser (Arquitetura):",
                "Topologia em camadas, desacoplamento cálculo/LLM, LGPD e fronteira ética com o CRC.",
                True,
            ),
            (
                "Ingrid (DevOps & MLOps):",
                "CI/CD no GitHub Actions, portal no GitHub Pages, governança de modelos e relatórios PDF.",
                True,
            ),
        ],
        bg_rgb=(0.95, 0.98, 1.0),
        border_rgb=(0.60, 0.75, 0.95),
    )

    doc.draw_section_title(
        "1. Jhessica — Ciência de Dados e Inteligência Artificial",
        "Modelagem de RAG factual, extração de entidades fiscais, engenharia de prompts e avaliação.",
        badge="CIÊNCIA DE DADOS",
    )

    doc.draw_paragraph(
        "Jhessica liderou a frente de inteligência do Sócio Digital, desenvolvendo o pipeline de ingestão e recuperação "
        "jurídica de ponta a ponta, projetado para garantir zero alucinação em matérias contábeis."
    )

    doc.draw_bullet(
        "Chunking Hierárquico Jurídico (src/rag/chunker.py):",
        "Particionamento de normas (LC 123/2006, CGSN 140/2018) respeitando Artigos, Parágrafos e Incisos, com injeção de contexto (Context Injection) para eliminar chunks descontextualizados.",
    )
    doc.draw_bullet(
        "Vector Store Híbrido com Fallback (src/rag/vector_store.py):",
        "Persistência em banco SQLite combinando busca por similaridade de cosseno (embeddings densos MiniLM) com 30% de correspondência léxica e suporte a fallback offline.",
    )
    doc.draw_bullet(
        "Extrator de Entidades Fiscais - NER (src/rag/entity_extractor.py):",
        "Classificação de intenções tributárias, extração automatizada de CNAEs, CNPJs, valores monetários (R$) e expansão de queries com sinônimos legais da Receita Federal.",
    )
    doc.draw_bullet(
        "RAGService com Guardrails (src/rag/service.py, prompts.py):",
        "Orquestrador central que une o RAG ao motor determinístico de cálculo, impondo formatação mandatória em planos de 3 passos, citações oficiais e abstenção contra fraudes.",
    )

    doc.draw_card(
        "Suítes de Testes e Validação Entregues por Jhessica",
        [
            (
                "test_pipeline.py:",
                "4/4 casos de recuperação canônica aprovados com 100% de precisão de contexto.",
                True,
            ),
            (
                "test_entity_extractor.py:",
                "5/5 casos de extração NER e teste de integração tripla aprovados.",
                True,
            ),
            (
                "test_rag_service.py:",
                "5/5 casos de governança, fidelidade factual (faithfulness) e abstenção ética aprovados.",
                True,
            ),
        ],
        bg_rgb=(0.96, 0.98, 0.96),
        border_rgb=(0.70, 0.88, 0.70),
    )

    # ========================================================
    # PÁGINA 2: ENGENHARIA DE DADOS (LUCAS) & ARQUITETURA
    # ========================================================
    doc.canvas.new_page()
    doc.y = 800
    doc.draw_page_header()

    doc.draw_section_title(
        "2. Lucas — Engenharia de Dados & Desenvolvimento (Dev)",
        "Ingestão estruturada da LC 123/2006, base de CNAEs, motor determinístico e API FastAPI.",
        badge="DADOS & BACKEND",
    )

    doc.draw_paragraph(
        "Lucas estruturou o alicerce matemático e cadastral do projeto, garantindo que o sistema processe alíquotas oficiais "
        "com total exatidão e forneça consultas ágeis de atividades econômicas."
    )

    doc.draw_bullet(
        "Ingestão de Tabelas da LC 123/2006 (data/raw/tabelas_simples_nacional.json):",
        "Estruturação das 30 faixas fiscais dos Anexos I, II, III, IV e V, incluindo alíquotas nominais e parcelas a deduzir oficiais.",
    )
    doc.draw_bullet(
        "Base de CNAEs do IBGE (data/raw/cnaes_base.json):",
        "Catalogação saneada de 46 subclasses de CNAEs com marcações de elegibilidade ao MEI e sujeição ao Fator R.",
    )
    doc.draw_bullet(
        "Repositório com Busca FTS5 (src/fiscal/repository.py):",
        "Banco relacional SQLite (fiscal.db) com índice de texto completo (Full-Text Search) para localização instantânea de CNAEs por palavras-chave.",
    )
    doc.draw_bullet(
        "Motor Fiscal Determinístico (src/fiscal/calculator.py):",
        "Implementação da fórmula oficial da alíquota efetiva, cálculo exato do Fator R (>= 28%), comparativo de economia e validação de excesso de faturamento no MEI (> 20%).",
    )
    doc.draw_bullet(
        "Pesquisa de Fontes e Crawler (docs/arquitetura/crawler-arquitetura.md, exploracao-dados.md):",
        "Mapeamento das fontes governamentais e desenho arquitetural do coletor por fonte.",
    )
    doc.draw_bullet(
        "API REST FastAPI (api/app/main.py):",
        "Construção do template de backend em FastAPI e conteinerização Docker.",
    )

    doc.draw_card(
        "Validação do Motor Determinístico Fiscal (Lucas)",
        [
            (
                "test_fiscal.py:",
                "6/6 casos canônicos de simulação fiscal aprovados com 100% de exatidão matemática.",
                True,
            ),
            (
                "Integração:",
                "O RAGService consome diretamente o FiscalCalculator, sem risco de alucinação numérica.",
                True,
            ),
        ],
        bg_rgb=(0.95, 0.98, 1.0),
        border_rgb=(0.60, 0.75, 0.95),
    )

    doc.draw_section_title(
        "3. Clara e Nasser — Arquitetura de Soluções",
        "Topologia desacoplada, contratos de dados, modelo de segurança e fronteira ética com o CRC.",
        badge="ARQUITETURA",
    )

    doc.draw_bullet(
        "Topologia em Três Camadas (docs/arquitetura/arquitetura.md):",
        "Desacoplamento estrito entre Camada de Dados (Lucas), Camada de Inteligência/RAG (Jhessica) e Camada de Serviços/Backend.",
    )
    doc.draw_bullet(
        "Diretriz de Ouro do Sistema:",
        "O LLM é expressamente proibido de calcular alíquotas de cabeça; toda conta matemática é delegada ao motor determinístico em Python.",
    )
    doc.draw_bullet(
        "Fronteira Ética com o CRC (Decreto-Lei nº 9.295/1946):",
        "Definição dos limites de atuação consultiva, garantindo que o copiloto atue no letramento sem usurpar prerrogativas exclusivas de contadores habilitados.",
    )
    doc.draw_bullet(
        "Requisitos Não Funcionais (RNFs):",
        "Especificação de segurança multi-tenant (RNF01), conformidade estrita com LGPD (RNF02) e tratamento de incertezas (RNF04).",
    )

    # ========================================================
    # PÁGINA 3: DEVOPS/MLOPS (INGRID) & MATRIZ DE INTEGRAÇÃO
    # ========================================================
    doc.canvas.new_page()
    doc.y = 800
    doc.draw_page_header()

    doc.draw_section_title(
        "4. Ingrid — Ops (DevOps & MLOps)",
        "Esteiras de CI/CD, governança de modelos/dados, GitHub Pages e consolidação de entregáveis.",
        badge="DEVOPS & MLOPS",
    )

    doc.draw_bullet(
        "Automação de GitHub Pages (.github/workflows/pages.yml):",
        "Deploy contínuo e automático da documentação no padrão Docs-as-Code via Docsify com suporte nativo a diagramas Mermaid.",
    )
    doc.draw_bullet(
        "Pacote de Definição do Projeto (docs/projeto/definicao-projeto.md):",
        "Formalização do problema, Essential Question, mapa de stakeholders, personas (Carlos, Mariana, Rafael), riscos e catálogo de 12 RFs e 10 RNFs.",
    )
    doc.draw_bullet(
        "Fundamentação de Qualidade de Vida (docs/projeto/guiding-questions.md):",
        "Vínculo do terror fiscal e sobrecarga administrativa ao estresse crônico dos pequenos empreendedores.",
    )
    doc.draw_bullet(
        "Planejamento MLOps (docs/arquitetura/devops-mlops.md):",
        "Arquitetura da esteira de integração contínua para validação de fidelidade (Ragas/MLflow) e versionamento de dados via DVC.",
    )
    doc.draw_bullet(
        "Consolidação dos Entregáveis em PDF:",
        "Diagramação e publicação oficial dos relatórios formais da Residência em IA.",
    )

    doc.draw_section_title(
        "5. Matriz de Integração dos Componentes do Grupo 08",
        "Como as frentes se conectam operacionalmente no repositório.",
    )

    headers = ["Componente", "Responsável", "Integração no Sistema", "Status"]
    widths = [115, 95, 205, 90.28]
    rows = [
        [
            "Tabelas Simples e CNAEs",
            "Lucas",
            "Base de dados consultada por FTS5 e cálculos.",
            "100% Concluído",
        ],
        [
            "Motor Determinístico",
            "Lucas",
            "Executa alíquotas efetivas e regra do Fator R.",
            "100% Concluído",
        ],
        [
            "Chunking e Vector Store",
            "Jhessica",
            "Indexação hierárquica e busca híbrida de leis.",
            "100% Concluído",
        ],
        [
            "NER Fiscal e Guardrails",
            "Jhessica",
            "Extração de parâmetros e filtro anti-alucinação.",
            "100% Concluído",
        ],
        [
            "RAGService",
            "Jhessica",
            "Une Vector Store ao Motor Fiscal e gera 3 passos.",
            "100% Concluído",
        ],
        [
            "Topologia Desacoplada",
            "Clara / Nasser",
            "Garante respeito aos contratos e fronteira CRC.",
            "100% Aderente",
        ],
        [
            "Docsify e GitHub Pages",
            "Ingrid",
            "Publicação contínua da documentação e relatórios.",
            "Ativo no Pages",
        ],
    ]
    doc.draw_table(headers, rows, widths)

    doc.draw_section_title(
        "6. Conclusão e Prontidão para a Próxima Fase",
        "Status de prontidão para unificação e deploy.",
    )

    doc.draw_card(
        "Declaração de Alinhamento e Prontidão Técnica",
        [
            (
                "Integração Total:",
                "O repositório possui 100% de cobertura nos testes fiscais, de extração e de RAG.",
                False,
            ),
            (
                "Fase 2 (Dados e Modelagem):",
                "Concluída com êxito pleno em conformidade com as diretrizes do Challenge 2.",
                True,
            ),
            (
                "Próximo Passo Conjunto:",
                "Lucas expor o RAGService na API FastAPI e Ingrid plugar o CI no GitHub Actions.",
                True,
            ),
        ],
        bg_rgb=(0.95, 0.98, 1.0),
        border_rgb=(0.10, 0.28, 0.65),
    )

    doc.canvas.save()
    print(f"PDF de Entregas da Equipe gerado com sucesso em: {pdf_path}")


if __name__ == "__main__":
    generate_document()
