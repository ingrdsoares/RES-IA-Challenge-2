from pathlib import Path

from app.assistant.agents.declaration import read_declaration

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "benchmark" / "multimodal"


def test_reads_dasn_with_excess_as_decimal_strings():
    reading, usage = read_declaration((FIXTURES / "dasn_simei_excesso_92k.pdf").read_bytes())
    assert reading.model_dump(mode="json") == {
        "legible": True,
        "ano_calendario": 2025,
        "cnpj": "12.345.678/0001-90",
        "razao_social": "SILVA SERVICOS DE TECNOLOGIA LTDA MEI",
        "receita_total": "92000.00",
        "limite_anual": "81000.00",
        "excesso_valor": "11000.00",
        "excesso_percentual": "13.58",
        "faixa_excesso": "ate_20_porcento",
        "efeito_enquadramento": "desenquadramento_ano_subsequente",
        "data_efeito": "2026-01-01",
        "fundamentacao_legal": ("Art. 18-A da LC 123/2006 e Art. 115 da Resolução CGSN 140/2018"),
    }
    assert usage["model"] == "dasn-pdf-parser"
    assert usage["input_tokens"] == 0 and usage["output_tokens"] == 0


def test_regular_dasn_has_no_excess():
    reading, _ = read_declaration((FIXTURES / "extrato_das_regular_60k.pdf").read_bytes())
    assert reading.legible is True
    assert reading.model_dump(mode="json")["receita_total"] == "60000.00"
    assert reading.faixa_excesso == "dentro_do_limite"
    assert reading.data_efeito is None


def test_unreadable_pdf_is_marked_illegible_without_values():
    reading, _ = read_declaration(b"%PDF-1.4 corrompido")
    assert reading.legible is False
    assert reading.receita_total is None
    assert reading.faixa_excesso is None
