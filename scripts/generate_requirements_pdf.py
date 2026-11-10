"""
Gerador de PDF Executivo — Sócio Digital: Análise de Requisitos Críticos
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
                " An\xe1lise de Requisitos Cr\xedticos | RES-IA Challenge 2"
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
            " PACOTE DE DEFINI\xc7\xc3O T\xc9CNICA) Tj ET"
        )
        ops.append(
            "BT /F1 8 Tf 0.45 0.52 0.60 rg 440 814 Td (RES-IA | Challenge 2 \x97 Grupo 08) Tj ET"
        )
        self.y = 788

    def draw_cover_banner(self):
        ops = self.canvas.current_page_ops
        # Main background rect
        ops.append("q 0.06 0.12 0.28 rg 45 745 505.28 65 re f Q")
        # Gold accent line on top
        ops.append("q 0.85 0.65 0.13 rg 45 807 505.28 3 re f Q")

        # Titles inside banner
        ops.append(
            "BT /F2 15 Tf 1 1 1 rg 60 782 Td (S\xd3CIO DIGITAL: COPILOTO DE GEST\xc3O FISCAL) Tj ET"
        )
        ops.append(
            "BT /F1 9 Tf 0.85 0.90 0.98 rg 60 766 Td (RES-IA Challenge 2 \x97"
            " Grupo 08 | Clara, Ingrid, Jhessica, Lucas, Nasser) Tj ET"
        )
        ops.append(
            "BT /F2 8.5 Tf 0.95 0.75 0.25 rg 60 752 Td (AN\xc1LISE T\xc9CNICA:"
            " QUAL \xc9 O PRINCIPAL REQUISITO DO PROJETO?) Tj ET"
        )
        self.y = 726

    def draw_section_title(self, title, subtitle=None):
        self.check_space(40)
        ops = self.canvas.current_page_ops
        # Left accent pill bar
        ops.append(f"q 0.10 0.28 0.65 rg 45 {self.y - 13} 4 15 re f Q")
        # Title text
        escaped_title = escape_pdf_text(title)
        ops.append(f"BT /F2 11 Tf 0.08 0.14 0.25 rg 55 {self.y - 11} Td ({escaped_title}) Tj ET")
        self.y -= 17

        if subtitle:
            escaped_sub = escape_pdf_text(subtitle)
            ops.append(f"BT /F3 8.5 Tf 0.40 0.45 0.55 rg 55 {self.y - 7} Td ({escaped_sub}) Tj ET")
            self.y -= 13
        self.y -= 3

    def draw_card(self, title, items, bg_rgb=(0.96, 0.98, 1.0), border_rgb=(0.75, 0.85, 0.95)):
        """
        items is a list of tuples: (prefix_bold, normal_text, is_bullet)
        """
        max_chars = 95
        rendered_lines = []
        for prefix, text, is_bullet in items:
            if not prefix and not text:
                rendered_lines.append(("", "", False, True))  # blank line
                continue

            # wrap text
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
                # draw subtle square bullet
                ops.append(f"q 0.20 0.40 0.70 rg 58 {cur_text_y + 2} 3 3 re f Q")
                indent_x = 66
            elif not prefix and indent_x == 57:
                # line continuation
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
                f"BT /{font} {size} Tf {r:.2f} {g:.2f} {b:.2f} rg {self.left}"
                f" {self.y - size} Td ({escaped}) Tj ET"
            )
            self.y -= leading
        self.y -= 3

    def draw_bullet(self, bold_prefix, text, size=8.5, leading=11.5):
        max_chars = int((self.usable_width - 18) / (size * 0.52))
        sub_lines = wrap_text(text, max_chars - len(bold_prefix) - 2)

        req_h = (1 + len(sub_lines) - 1) * leading
        self.check_space(req_h + 4)

        ops = self.canvas.current_page_ops
        # Draw vector square bullet
        bullet_y = self.y - size + 2
        ops.append(f"q 0.15 0.35 0.70 rg {self.left + 2} {bullet_y} 3.5 3.5 re f Q")

        # First line with bold prefix
        e_bp = escape_pdf_text(bold_prefix)
        first_content = sub_lines[0] if sub_lines else ""
        e_rem = escape_pdf_text(" " + first_content if first_content else "")
        ops.append(
            f"BT /F2 {size} Tf 0.10 0.15 0.25 rg {self.left + 12} {self.y - size} Td ({e_bp}) Tj /F1 {size} Tf 0.20 0.25 0.35 rg ({e_rem}) Tj ET"
        )
        self.y -= leading

        # Continuation lines
        for sub_line in sub_lines[1:]:
            e_l = escape_pdf_text(sub_line)
            ops.append(
                f"BT /F1 {size} Tf 0.20 0.25 0.35 rg {self.left + 12} {self.y - size} Td ({e_l}) Tj ET"
            )
            self.y -= leading
        self.y -= 2

    def draw_table(self, headers, rows, col_widths):
        # Calculate dynamic row heights based on text wrapping
        table_rows_data = []
        total_h = 20  # header height
        for r_idx, r_data in enumerate(rows):
            # calculate lines per cell
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
    pdf_path = Path("/Users/aluno2/RES-IA-Challenge-2/docs/requisito-principal-socio-digital.pdf")
    doc = DocumentBuilder(str(pdf_path))

    # --- PÁGINA 1 ---
    doc.draw_cover_banner()

    doc.draw_card(
        "A Pergunta Central do Avaliador / Stakeholder",
        [
            (
                "",
                '"Qual o principal requisito do meu projeto? Aquele que, se faltar, o projeto simplesmente não funcionaria?"',
                False,
            ),
            ("", "", False),
            (
                "Resposta Executiva:",
                "O Sócio Digital não é apenas um assistente de conversação comum; é um copiloto de conformidade e tomada de decisão tributária. Seu funcionamento apoia-se em um TRINÔMIO DE REQUISITOS VITAIS:",
                False,
            ),
            (
                "1. Entrada de Negócio (RF01):",
                "Contexto Empresarial (CNAE / Faturamento / Folha). Sem ele, inexiste base matemática e legal.",
                True,
            ),
            (
                "2. Núcleo Arquitetural (RF03 / RNF05):",
                "RAG Factual + Motor Determinístico. Sem ele, a IA alucina e gera multas ao usuário.",
                True,
            ),
            (
                "3. Entrega de Valor (RF07):",
                "Planos de Ação Estruturados em 3 Etapas. Sem ele, o sistema vira um chat descartável sem utilidade.",
                True,
            ),
        ],
        bg_rgb=(0.95, 0.98, 1.0),
        border_rgb=(0.60, 0.75, 0.95),
    )

    doc.draw_section_title(
        "1. O Requisito Vital de Entrada: Cadastro do Contexto Empresarial (RF01)",
        "Sem dados cadastrais e financeiros, a legislação tributária brasileira torna-se inaplicável.",
    )
    doc.draw_paragraph(
        "No sistema tributário nacional regido pela Lei Complementar nº 123/2006, é impossível emitir qualquer orientação "
        "ou apuração contábil no vácuo. Toda regra fiscal depende estritamente do cruzamento simultâneo de quatro variáveis "
        "cadastradas no perfil da empresa:"
    )

    doc.draw_bullet(
        "CNAE (Classificação Nacional de Atividades):",
        "Determina de forma taxativa se o negócio pode ser MEI ou se obrigatoriamente deve migrar para o Simples Nacional. Além disso, vincula a atividade aos Anexos de I a V da LC 123/2006.",
    )
    doc.draw_bullet(
        "Faturamento Bruto Acumulado (RBT12):",
        "A apuração do Simples Nacional não usa alíquota fixa. Exige a fórmula oficial: Alíquota Efetiva = ((RBT12 * Alíquota Nominal) - Parcela a Deduzir) / RBT12. Sem o RBT12, a alíquota não existe.",
    )
    doc.draw_bullet(
        "Folha de Pagamento e Pró-Labore (Fator R):",
        "Para empresas de serviços (tecnologia, engenharia, saúde), se a razão entre folha e faturamento for >= 28%, a empresa tributa no Anexo III (6%); se for menor, cai no Anexo V (15,5%).",
    )
    doc.draw_bullet(
        "Localização Municipal e Estadual:",
        "Define a incidência de ISS ou ICMS e a aplicação de sublimites fiscais estaduais.",
    )

    doc.draw_card(
        "O que acontece se faltar o Contexto Empresarial (RF01)?",
        [
            (
                "Impacto 1:",
                "Qualquer orientação contábil torna-se puro palpite genérico e juridicamente perigoso.",
                True,
            ),
            (
                "Impacto 2:",
                "O usuário pode pagar 15,5% de imposto em vez de 6% por desconhecer a aplicação do Fator R.",
                True,
            ),
            (
                "Impacto 3:",
                "O empreendedor corre o risco de desenquadramento retroativo do MEI com multa de 20% e juros SELIC.",
                True,
            ),
        ],
        bg_rgb=(1.0, 0.96, 0.96),
        border_rgb=(0.95, 0.70, 0.70),
    )

    # --- PÁGINA 2 ---
    doc.canvas.new_page()
    doc.y = 800
    doc.draw_page_header()

    doc.draw_section_title(
        "2. O Requisito Arquitetural Inegociável: RAG Factual + Motor Determinístico (RF03 / RNF05)",
        "A fronteira de segurança entre inteligência generativa e exatidão contábil (Zero Alucinação).",
    )
    doc.draw_paragraph(
        "O maior risco mapeado pelo Grupo 08 na concepção do Sócio Digital é a ALUCINAÇÃO DO LLM. Modelos fundacionais são "
        "motores probabilísticos de texto: eles tendem a inventar alíquotas plausíveis, errar contas com decimais e citar artigos "
        "revogados. Na contabilidade, um erro de R$ 0,01 invalida o Documento de Arrecadação do Simples Nacional (DAS)."
    )

    doc.draw_card(
        "A Solução Arquitetural de Clara, Nasser, Lucas e Jhessica",
        [
            (
                "1. Ingestão e Vector Store Factual (src/rag/):",
                "A legislação oficial (LC 123/2006, CGSN 140/2018) é indexada por dispositivos jurídicos canônicos. Cada chunk preserva o artigo, parágrafo, órgão emissor e período de vigência.",
                False,
            ),
            (
                "2. Motor Determinístico em Python (src/fiscal/):",
                "As regras matemáticas de dedução, alíquotas efetivas e enquadramento do MEI são 100% determinísticas em código Python (FiscalCalculator). O LLM é expressamente proibido de calcular impostos.",
                False,
            ),
            (
                "3. Papel do LLM na Solução:",
                "O modelo generativo apenas recebe os números calculados pelo motor determinístico e o texto oficial resgatado pelo RAG para sintetizar uma explicação acolhedora, didática e livre de jargões técnicos.",
                False,
            ),
        ],
        bg_rgb=(0.96, 0.98, 0.96),
        border_rgb=(0.70, 0.88, 0.70),
    )

    doc.draw_section_title(
        "3. O Requisito de Entrega de Valor: Planos de Ação em até 3 Passos (RF07)",
        "A superação do modelo de chat comum: transformando ansiedade em passos executáveis.",
    )
    doc.draw_paragraph(
        "Pequenos empresários vivem sobrecarregados de tarefas operacionais e sob constante terror fiscal. Um chat tradicional "
        "que responde longas explicações teóricas gera paralisia por análise. O diferencial do projeto é o requisito RF07, "
        "que converte toda resposta em no máximo 3 etapas acionáveis:"
    )

    doc.draw_bullet(
        "Passo 1 (Diagnóstico):",
        "Identificar a pendência exata na base oficial (ex.: Notificação de Débito no Portal e-CAC).",
    )
    doc.draw_bullet(
        "Passo 2 (Execução):",
        "Instrução objetiva do que fazer (ex.: Como aderir ao Programa de Parcelamento do Simples Nacional).",
    )
    doc.draw_bullet(
        "Passo 3 (Comprovação):",
        "Como obter a Certidão Positiva com Efeito de Negativa (CPEN) para manter o negócio apto a emitir notas.",
    )

    doc.draw_section_title(
        "4. A Fronteira Regulatória e Ética: Não Exercício Ilegal da Contabilidade (RNF04)",
        "O assistente empodera o empreendedor sem violar prerrogativas exclusivas do CRC.",
    )
    doc.draw_paragraph(
        "O Decreto-Lei nº 9.295/1946 reserva privativamente a contadores registrados no CRC a emissão de balanços e pareceres fiscais. "
        "O Sócio Digital foi desenhado sob o requisito RNF04 (Abstenção e Disclaimers): atua no letramento e organização fiscal prévia, "
        "e se abstém proativamente, recomendando a validação presencial com o contador em operações societárias complexas."
    )

    # --- PÁGINA 3 ---
    doc.canvas.new_page()
    doc.y = 800
    doc.draw_page_header()

    doc.draw_section_title(
        "5. Matriz Comparativa: O Impacto da Ausência de Cada Requisito",
        "Visão sintetizada de dependência funcional, tecnológica e de governança.",
    )

    headers = ["Requisito", "Tipo / Camada", "Objetivo no Projeto", "Impacto se Inexistir"]
    widths = [80, 95, 175, 155.28]
    rows = [
        [
            "RF01: Contexto",
            "Funcional (Entrada)",
            "Capturar CNAE, RBT12, porte e folha salarial.",
            "Cálculos impossíveis; respostas genéricas inválidas.",
        ],
        [
            "RF03: RAG Factual",
            "Funcional (IA/Dados)",
            "Ancorar respostas em normas oficiais vigentes.",
            "Alucinação jurídica com normas revogadas.",
        ],
        [
            "RNF05: Motor Python",
            "Arquitetura / Regras",
            "Executar Fator R e alíquotas com exatidão matemática.",
            "Erros de centavos que invalidam guias DAS oficiais.",
        ],
        [
            "RF07: Planos 3 Passos",
            "Funcional (UX/Entrega)",
            "Converter dúvidas em tarefas acionáveis e claras.",
            "Usuário perdido em textos longos; abandono do app.",
        ],
        [
            "RF06: Painel Semáforo",
            "Funcional (Gestão)",
            "Acompanhar conformidade e alertar vencimentos.",
            "Usuário perde prazos e acumula multas moratórias.",
        ],
        [
            "RNF04: Abstenção CRC",
            "Não-Funcional (Ético)",
            "Respeitar prerrogativas do profissional contábil.",
            "Processos judiciais por exercício ilegal da profissão.",
        ],
    ]
    doc.draw_table(headers, rows, widths)

    doc.draw_section_title(
        "6. Conclusão e Resumo para Defesa Técnica",
        "Como sintetizar a resposta diante da banca avaliadora da Residência em IA.",
    )

    doc.draw_card(
        "Declaração de Encerramento e Defesa do Grupo 08",
        [
            (
                "Defesa:",
                '"Se fôssemos forçados a eleger um único requisito sem o qual o projeto sequer existiria, a resposta é o',
                False,
            ),
            (
                "NÚCLEO VITAL:",
                "DESACOPLAMENTO ENTRE O CONTEXTO EMPRESARIAL (RF01) E O MOTOR DETERMINÍSTICO ANCORADO EM RAG (RF03/RNF05).",
                False,
            ),
            ("", "", False),
            (
                "1. O modelo generativo isolado",
                "destrói a confiança do empreendedor porque não sabe calcular tributos.",
                True,
            ),
            (
                "2. A calculadora fria de impostos",
                "sem IA não ajuda o leigo que tem pavor de guias e termos contábeis.",
                True,
            ),
            ("", "", False),
            (
                "A essência do Sócio Digital",
                'é unir o rigor matemático da LC 123/2006 à capacidade do LLM de traduzir a burocracia em um plano acolhedor de 3 passos, libertando o microempreendedor do terror fiscal e devolvendo sua qualidade de vida."',
                False,
            ),
        ],
        bg_rgb=(0.95, 0.98, 1.0),
        border_rgb=(0.10, 0.28, 0.65),
    )

    doc.canvas.save()
    print(f"PDF gerado com sucesso em: {pdf_path}")


if __name__ == "__main__":
    generate_document()
