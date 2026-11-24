"""
Extrator determinístico de documentos fiscais PDF (DASN-SIMEI e Extratos PGMEI).
Sócio Digital — RES-IA Challenge 2 (Grupo 08).
"""

import io
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from app.assistant.multimodal.schemas import MultimodalDocumentResult


def parse_currency(val_str: Optional[str]) -> float:
    """Converte strings monetárias no padrão brasileiro (ex.: 'R$ 92.000,00' ou '60.000,00') para float."""
    if not val_str:
        return 0.0
    cleaned = re.sub(r"[^\d,\.]", "", val_str)
    if not cleaned:
        return 0.0
    # Se houver ponto e vírgula (ex.: 92.000,00)
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


class MultimodalPDFParser:
    """Parser para extração de dados fiscais de PDFs (com foco em DASN-SIMEI do MEI)."""

    def __init__(self, limite_anual_mei: float = 81000.0):
        self.limite_anual_mei = limite_anual_mei

    def extract_text(self, source: Union[str, Path, bytes, io.BytesIO]) -> str:
        """Extrai texto integral do arquivo PDF."""
        if not PYPDF_AVAILABLE:
            raise RuntimeError("A biblioteca 'pypdf' é necessária para processamento de arquivos PDF.")

        if isinstance(source, (str, Path)):
            with open(source, "rb") as f:
                reader = pypdf.PdfReader(f)
                return self._read_pages(reader)
        elif isinstance(source, bytes):
            stream = io.BytesIO(source)
            reader = pypdf.PdfReader(stream)
            return self._read_pages(reader)
        elif isinstance(source, io.BytesIO):
            reader = pypdf.PdfReader(source)
            return self._read_pages(reader)
        else:
            raise ValueError(f"Formato de fonte não suportado: {type(source)}")

    def _read_pages(self, reader: "pypdf.PdfReader") -> str:
        pages_text = []
        for p in reader.pages:
            t = p.extract_text()
            if t:
                pages_text.append(t)
        return "\n".join(pages_text)

    def parse(
        self, source: Union[str, Path, bytes, io.BytesIO], raise_on_error: bool = False
    ) -> MultimodalDocumentResult:
        """Processa o PDF e retorna o resultado fiscal estruturado."""
        try:
            raw_text = self.extract_text(source)
        except Exception as e:
            if raise_on_error:
                raise
            return MultimodalDocumentResult(
                document_type="UNKNOWN",
                texto_bruto="",
                metadados_adicionais={"error": str(e)},
                confianca=0.0,
            )

        if not raw_text.strip():
            return MultimodalDocumentResult(
                document_type="UNKNOWN",
                texto_bruto="",
                metadados_adicionais={"warning": "PDF sem texto extraível"},
                confianca=0.0,
            )

        # Identificação do Tipo de Documento
        doc_type = "UNKNOWN"
        if "DASN-SIMEI" in raw_text or "DECLARAÇÃO ANUAL SIMPLIFICADA PARA O MEI" in raw_text:
            doc_type = "DASN-SIMEI"
        elif "PGMEI" in raw_text or "SIMEI" in raw_text:
            doc_type = "PGMEI"

        # Extração de Identificadores
        recibo_match = re.search(r"Número do Recibo:\s*([0-9\.\-]+)", raw_text, re.IGNORECASE)
        recibo = recibo_match.group(1).strip() if recibo_match else None

        ano_match = re.search(r"Ano-Calend[aá]rio:\s*(\d{4})", raw_text, re.IGNORECASE)
        ano_calendario = int(ano_match.group(1)) if ano_match else None

        tipo_dec_match = re.search(r"Tipo de Declara[çc][aã]o:\s*([A-Za-z]+)", raw_text, re.IGNORECASE)
        tipo_declaracao = tipo_dec_match.group(1).strip() if tipo_dec_match else "Original"

        cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        cnpj = cnpj_match.group(1).strip() if cnpj_match else None

        razao_match = re.search(
            r"Raz[aã]o Social:\s*(.+?)(?:\s+3\.|\s+CNAE|\s+Possui|\n)", raw_text, re.IGNORECASE
        )
        razao_social = razao_match.group(1).strip() if razao_match else None

        cnae_match = re.search(r"CNAE Principal:\s*([0-9]{4}-[0-9]/[0-9]{2})", raw_text, re.IGNORECASE)
        cnae = cnae_match.group(1).strip() if cnae_match else None

        emp_match = re.search(r"Possuiu Empregado:\s*(Sim|N[aã]o)", raw_text, re.IGNORECASE)
        possui_empregado = (
            True if emp_match and emp_match.group(1).lower().startswith("s") else False
        )

        # Extração de Receitas
        # Campo 01: Comércio
        comercio_match = re.search(
            r"Campo 01[^\n]*?Com[eé]rcio[^\n]*?:\s*(R\$\s*[\d\.,]+)", raw_text, re.IGNORECASE
        )
        receita_comercio = parse_currency(comercio_match.group(1)) if comercio_match else 0.0

        # Campo 02: Serviços
        servicos_match = re.search(
            r"Campo 02[^\n]*?Servi[çc]os[^\n]*?:\s*(R\$\s*[\d\.,]+)", raw_text, re.IGNORECASE
        )
        receita_servicos = parse_currency(servicos_match.group(1)) if servicos_match else 0.0

        # Total
        total_match = re.search(
            r"TOTAL DA RECEITA BRUTA DECLARADA:\s*(R\$\s*[\d\.,]+)", raw_text, re.IGNORECASE
        )
        if total_match:
            receita_total = parse_currency(total_match.group(1))
        else:
            receita_total = receita_comercio + receita_servicos

        # Apuração Fiscal do MEI
        excesso_valor = max(0.0, receita_total - self.limite_anual_mei)
        excesso_percentual = (
            round((excesso_valor / self.limite_anual_mei) * 100, 2)
            if self.limite_anual_mei > 0
            else 0.0
        )

        limite_tolerancia_20 = self.limite_anual_mei * 1.20  # R$ 97.200,00

        if excesso_valor == 0.0:
            faixa = "dentro_do_limite"
            efeito = "manutencao_simei"
            data_efeito = None
            base_legal = "Art. 18-A da LC 123/2006"
        elif receita_total <= limite_tolerancia_20:
            faixa = "ate_20_porcento"
            efeito = "desenquadramento_ano_subsequente"
            data_efeito = f"{ano_calendario + 1}-01-01" if ano_calendario else "ano_subsequente"
            base_legal = "Art. 18-A da LC 123/2006 e Art. 115 da Resolução CGSN 140/2018"
        else:
            faixa = "acima_20_porcento"
            efeito = "desenquadramento_retroativo"
            data_efeito = f"{ano_calendario}-01-01" if ano_calendario else "ano_corrente"
            base_legal = "Art. 18-A, § 7º da LC 123/2006 e Art. 115 da Resolução CGSN 140/2018"

        return MultimodalDocumentResult(
            document_type=doc_type,
            numero_recibo=recibo,
            ano_calendario=ano_calendario,
            tipo_declaracao=tipo_declaracao,
            cnpj=cnpj,
            razao_social=razao_social,
            cnae_principal=cnae,
            possui_empregado=possui_empregado,
            receita_comercio=receita_comercio,
            receita_servicos=receita_servicos,
            receita_total=receita_total,
            limite_anual=self.limite_anual_mei,
            excesso_valor=excesso_valor,
            excesso_percentual=excesso_percentual,
            faixa_excesso=faixa,
            efeito_enquadramento=efeito,
            data_efeito=data_efeito,
            fundamentacao_legal=base_legal,
            texto_bruto=raw_text,
            confianca=0.98 if cnpj and receita_total > 0 else 0.70,
        )
