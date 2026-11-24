#!/usr/bin/env python3
"""
Script de Geração de Documentos Fiscais para Benchmark Multimodal (Challenge 2)
Cria arquivos PDF padronizados da DASN-SIMEI (Declaração Anual do MEI) para testes de extração.
"""

import os
import sys

class PDFCanvas:
    def __init__(self, filename):
        self.filename = filename
        self.pages = []
        self.current_page_ops = []
        self.width = 595.28   # A4
        self.height = 841.89

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

        page_obj_ids = []
        content_obj_ids = []
        current_id = 5
        for _ in range(total_pages):
            page_obj_ids.append(current_id)
            content_obj_ids.append(current_id + 1)
            current_id += 2

        obj_catalog = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
        kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
        obj_pages = f"<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>"
        obj_font_reg = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        obj_font_bold = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"

        objs = [obj_catalog, obj_pages, obj_font_reg, obj_font_bold]

        for p_idx in range(total_pages):
            c_obj_id = content_obj_ids[p_idx]
            page_ops = list(self.pages[p_idx])

            # Footer
            page_ops.append("q 0.80 0.80 0.80 RG 0.5 w 45 40 m 550.28 40 l S Q")
            page_ops.append(
                "BT /F1 7.5 Tf 0.40 0.40 0.40 rg 45 28 Td (DASN-SIMEI \x97 Documento Gerado para Benchmark de IA Multimodal | S\xf3cio Digital Grupo 08) Tj ET"
            )
            p_num = f"P\xe1gina {p_idx + 1} de {total_pages}"
            page_ops.append(f"BT /F1 7.5 Tf 0.40 0.40 0.40 rg 490 28 Td ({p_num}) Tj ET")

            stream_content = "\n".join(page_ops)
            stream_bytes = stream_content.encode("latin1")
            stream_len = len(stream_bytes)

            obj_page = (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Contents {c_obj_id} 0 R /Resources << /Font << /F1 {font_reg_id} 0 R /F2 {font_bold_id} 0 R >> >> >>"
            )
            obj_stream = f"<< /Length {stream_len} >>\nstream\n{stream_content}\nendstream"
            objs.append(obj_page)
            objs.append(obj_stream)

        os.makedirs(os.path.dirname(os.path.abspath(self.filename)), exist_ok=True)
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


def escape_pdf(s):
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


def generate_dasn_pdf(filename, data):
    canvas = PDFCanvas(filename)
    canvas.new_page()
    ops = canvas.current_page_ops

    # Header Box (Receita Federal / Simples Nacional)
    ops.append("q 0.08 0.20 0.40 rg 45 745 505.28 65 re f Q")
    ops.append("q 1 0.80 0 rg 45 807 505.28 3 re f Q")

    ops.append(f"BT /F2 13 Tf 1 1 1 rg 60 782 Td ({escape_pdf('SECRETARIA DA RECEITA FEDERAL DO BRASIL')}) Tj ET")
    ops.append(f"BT /F2 10 Tf 0.90 0.95 1 rg 60 766 Td ({escape_pdf('SIMPLES NACIONAL \x97 SISTEMA DE RECOLHIMENTO EM VALORES FIXOS (SIMEI)')}) Tj ET")
    ops.append(f"BT /F1 8.5 Tf 0.80 0.88 0.98 rg 60 752 Td ({escape_pdf('DASN-SIMEI \x97 DECLARA\xc7\xc3O ANUAL SIMPLIFICADA PARA O MEI')}) Tj ET")

    y = 720

    def draw_section_box(title, y_top, height):
        ops.append(f"q 0.94 0.96 0.98 rg 0.70 0.78 0.88 RG 0.75 w 45 {y_top - height} 505.28 {height} re B Q")
        ops.append(f"q 0.10 0.25 0.50 rg 45 {y_top - 16} 505.28 16 re f Q")
        ops.append(f"BT /F2 8.5 Tf 1 1 1 rg 55 {y_top - 11.5} Td ({escape_pdf(title)}) Tj ET")

    # 1. Identificação da Declaração e Recibo
    draw_section_box("1. IDENTIFICA\xc7\xc3O DA DECLARA\xc7\xc3O E RECIBO DE ENTREGA", y, 55)
    y -= 28
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('N\xfamero do Recibo:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['recibo'])}) Tj ET")
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 330 {y} Td ({escape_pdf('Data/Hora de Transmiss\xe3o:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 445 {y} Td ({escape_pdf(data['data_transmissao'])}) Tj ET")
    y -= 14
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Tipo de Declara\xe7\xe3o:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['tipo_declaracao'])}) Tj ET")
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 330 {y} Td ({escape_pdf('Ano-Calend\xe1rio:')}) Tj ET")
    ops.append(f"BT /F2 8 Tf 0.10 0.35 0.70 rg 445 {y} Td ({escape_pdf(str(data['ano_calendario']))}) Tj ET")
    y -= 25

    # 2. Dados do Contribuinte (MEI)
    draw_section_box("2. DADOS CADASTRAIS DO MICROEMPREENDEDOR INDIVIDUAL", y, 55)
    y -= 28
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('CNPJ:')}) Tj ET")
    ops.append(f"BT /F2 8 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['cnpj'])}) Tj ET")
    y -= 14
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Raz\xe3o Social:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['razao_social'])}) Tj ET")
    y -= 25

    # 3. Informações de Atividade e Pessoal
    draw_section_box("3. ATIVIDADE ECON\xd4MICA E OCUPA\xc7\xc3O", y, 55)
    y -= 28
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('CNAE Principal:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['cnae_principal'])}) Tj ET")
    y -= 14
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Possuiu Empregado:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['possui_empregado'])}) Tj ET")
    y -= 25

    # 4. Demonstração de Receita Bruta (Valores Oficiais)
    draw_section_box("4. DEMONSTRA\xc7\xc3O DA RECEITA BRUTA DECLARADA", y, 110)
    y -= 28
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Campo 01 \x97 Receita Bruta de Com\xe9rcio / Ind\xfasteia:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 380 {y} Td ({escape_pdf(data['receita_comercio'])}) Tj ET")
    y -= 16
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Campo 02 \x97 Receita Bruta de Presta\xe7\xe3o de Servi\xe7os:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 380 {y} Td ({escape_pdf(data['receita_servicos'])}) Tj ET")
    y -= 16
    ops.append("q 0.70 0.78 0.88 RG 0.5 w 55 " + str(y + 4) + " m 535 " + str(y + 4) + " l S Q")
    ops.append(f"BT /F2 8.5 Tf 0.10 0.25 0.50 rg 55 {y - 4} Td ({escape_pdf('TOTAL DA RECEITA BRUTA DECLARADA:')}) Tj ET")
    ops.append(f"BT /F2 8.5 Tf 0.10 0.25 0.50 rg 380 {y - 4} Td ({escape_pdf(data['receita_total'])}) Tj ET")
    y -= 22
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Limite Legal do MEI (Art. 18-A LC 123/2006):')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 380 {y} Td ({escape_pdf('R$ 81.000,00')}) Tj ET")
    y -= 30

    # 5. Diagnóstico Fiscal Automático
    draw_section_box("5. SITUA\xc7\xc3O FISCAL IDENTIFICADA PELO ENQUADRAMENTO", y, 70)
    y -= 28
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Diagn\xf3stico:')}) Tj ET")
    ops.append(f"BT /F2 8 Tf 0.70 0.15 0.15 rg 145 {y} Td ({escape_pdf(data['diagnostico_status'])}) Tj ET")
    y -= 14
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Excesso Apurado:')}) Tj ET")
    ops.append(f"BT /F1 8 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['excesso_apurado'])}) Tj ET")
    y -= 14
    ops.append(f"BT /F2 8 Tf 0.15 0.20 0.30 rg 55 {y} Td ({escape_pdf('Efeito Legal:')}) Tj ET")
    ops.append(f"BT /F1 7.5 Tf 0.10 0.10 0.10 rg 145 {y} Td ({escape_pdf(data['efeito_legal'])}) Tj ET")
    y -= 25

    canvas.save()
    print(f"Documento gerado com sucesso: {filename}")


if __name__ == "__main__":
    out_dir = "/Users/aluno2/Documents/Grupo08/RES-IA-Challenge-2/data/benchmark/multimodal"
    os.makedirs(out_dir, exist_ok=True)

    # Documento 1: MEI de TI com excesso de faturamento (R$ 92.000,00)
    doc1_data = {
        "recibo": "98.76.54.32.10-99",
        "data_transmissao": "15/01/2026 14:32:10",
        "tipo_declaracao": "Original",
        "ano_calendario": 2025,
        "cnpj": "12.345.678/0001-90",
        "razao_social": "SILVA SERVICOS DE TECNOLOGIA LTDA MEI",
        "cnae_principal": "6201-5/01 - Desenvolvimento de programas de computador",
        "possui_empregado": "N\xe3o",
        "receita_comercio": "R$ 0,00",
        "receita_servicos": "R$ 92.000,00",
        "receita_total": "R$ 92.000,00",
        "diagnostico_status": "EXCESSO DE FATURAMENTO IDENTIFICADO (< 20%)",
        "excesso_apurado": "R$ 11.000,00 (13,58% acima do teto de R$ 81.000,00)",
        "efeito_legal": "Desenquadramento do SIMEI a partir de 01/01 do ano subsequente (Art. 115 CGSN 140/2018)"
    }
    generate_dasn_pdf(os.path.join(out_dir, "dasn_simei_excesso_92k.pdf"), doc1_data)

    # Documento 2: MEI de Comércio Regular (R$ 60.000,00)
    doc2_data = {
        "recibo": "87.65.43.21.09-88",
        "data_transmissao": "20/01/2026 10:15:00",
        "tipo_declaracao": "Original",
        "ano_calendario": 2025,
        "cnpj": "98.765.432/0001-10",
        "razao_social": "OLIVEIRA COMERCIO E VAREJO MEI",
        "cnae_principal": "4781-4/00 - Com\xe9rcio varejista de artigos do vestu\xe1rio",
        "possui_empregado": "N\xe3o",
        "receita_comercio": "R$ 60.000,00",
        "receita_servicos": "R$ 0,00",
        "receita_total": "R$ 60.000,00",
        "diagnostico_status": "REGULAR \x97 DENTRO DO LIMITE LEGAL",
        "excesso_apurado": "R$ 0,00 (Faturamento dentro do teto de R$ 81.000,00)",
        "efeito_legal": "Perman\xeancia assegurada no SIMEI para o exerc\xedcio seguinte"
    }
    generate_dasn_pdf(os.path.join(out_dir, "extrato_das_regular_60k.pdf"), doc2_data)
