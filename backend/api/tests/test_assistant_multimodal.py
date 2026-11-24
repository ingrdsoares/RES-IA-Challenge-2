"""
Testes unitários e de integração para o Extrator Multimodal de PDF (DASN-SIMEI).
Sócio Digital — RES-IA Challenge 2 (Grupo 08).
"""

import json
from pathlib import Path

import pytest
from app.assistant.multimodal.pdf_parser import MultimodalPDFParser, parse_currency
from app.assistant.multimodal.schemas import MultimodalDocumentResult


def _get_benchmark_dir() -> Path:
    current = Path(__file__).resolve().parent
    for p in [current, *current.parents]:
        target = p / "data" / "benchmark" / "multimodal"
        if target.exists():
            return target
    return Path(__file__).resolve().parents[3] / "data" / "benchmark" / "multimodal"


def _get_ground_truth(b_dir: Path) -> dict:
    gt_file = b_dir / "metadados_esperados.json"
    with open(gt_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def benchmark_dir() -> Path:
    return _get_benchmark_dir()


@pytest.fixture
def ground_truth(benchmark_dir: Path) -> dict:
    return _get_ground_truth(benchmark_dir)


def test_parse_currency():
    assert parse_currency("R$ 92.000,00") == 92000.0
    assert parse_currency("60.000,00") == 60000.0
    assert parse_currency("R$ 1.250,50") == 1250.50
    assert parse_currency("0,00") == 0.0
    assert parse_currency(None) == 0.0
    assert parse_currency("") == 0.0


def test_parse_dasn_simei_excesso_92k(benchmark_dir, ground_truth):
    pdf_path = benchmark_dir / "dasn_simei_excesso_92k.pdf"
    assert pdf_path.exists(), f"Arquivo de teste não encontrado: {pdf_path}"

    parser = MultimodalPDFParser()
    result = parser.parse(pdf_path)

    assert isinstance(result, MultimodalDocumentResult)
    assert result.document_type == "DASN-SIMEI"

    expected = ground_truth["casos_teste"][0]["dados_esperados"]
    assert result.cnpj == expected["cnpj"]
    assert result.ano_calendario == expected["ano_calendario"]
    assert result.receita_servicos == expected["receita_servicos"]
    assert result.receita_comercio == expected["receita_comercio"]
    assert result.receita_total == expected["receita_total"]
    assert result.excesso_valor == expected["excesso_valor"]
    assert result.excesso_percentual == expected["excesso_percentual"]
    assert result.faixa_excesso == expected["faixa_excesso"]
    assert result.efeito_enquadramento == expected["efeito_enquadramento"]
    assert result.confianca >= 0.95


def test_parse_dasn_simei_regular_60k(benchmark_dir, ground_truth):
    pdf_path = benchmark_dir / "extrato_das_regular_60k.pdf"
    assert pdf_path.exists(), f"Arquivo de teste não encontrado: {pdf_path}"

    parser = MultimodalPDFParser()
    result = parser.parse(pdf_path)

    assert isinstance(result, MultimodalDocumentResult)
    assert result.document_type == "DASN-SIMEI"

    expected = ground_truth["casos_teste"][1]["dados_esperados"]
    assert result.cnpj == expected["cnpj"]
    assert result.ano_calendario == expected["ano_calendario"]
    assert result.receita_comercio == expected["receita_comercio"]
    assert result.receita_servicos == expected["receita_servicos"]
    assert result.receita_total == expected["receita_total"]
    assert result.excesso_valor == expected["excesso_valor"]
    assert result.excesso_percentual == expected["excesso_percentual"]
    assert result.faixa_excesso == expected["faixa_excesso"]
    assert result.efeito_enquadramento == expected["efeito_enquadramento"]


def test_parse_from_bytes(benchmark_dir):
    pdf_path = benchmark_dir / "dasn_simei_excesso_92k.pdf"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    parser = MultimodalPDFParser()
    result = parser.parse(pdf_bytes)

    assert result.document_type == "DASN-SIMEI"
    assert result.cnpj == "12.345.678/0001-90"
    assert result.receita_total == 92000.0


def test_prompt_context_formatting(benchmark_dir):
    pdf_path = benchmark_dir / "dasn_simei_excesso_92k.pdf"
    parser = MultimodalPDFParser()
    result = parser.parse(pdf_path)

    context_str = result.to_prompt_context()
    assert "DASN-SIMEI" in context_str
    assert "12.345.678/0001-90" in context_str
    assert "92,000.00" in context_str or "92000.00" in context_str
    assert "ATE_20_PORCENTO" in context_str


def test_parse_invalid_pdf():
    parser = MultimodalPDFParser()
    result = parser.parse(b"NOT A VALID PDF CONTENT", raise_on_error=False)

    assert result.document_type == "UNKNOWN"
    assert result.confianca == 0.0
    assert "error" in result.metadados_adicionais


if __name__ == "__main__":
    b_dir = _get_benchmark_dir()
    gt = _get_ground_truth(b_dir)

    print("=== EXECUTANDO SUÍTE DE TESTES MULTIMODAL ===")
    test_parse_currency()
    print(" ✔ test_parse_currency: PASS")

    test_parse_dasn_simei_excesso_92k(b_dir, gt)
    print(" ✔ test_parse_dasn_simei_excesso_92k: PASS")

    test_parse_dasn_simei_regular_60k(b_dir, gt)
    print(" ✔ test_parse_dasn_simei_regular_60k: PASS")

    test_parse_from_bytes(b_dir)
    print(" ✔ test_parse_from_bytes: PASS")

    test_prompt_context_formatting(b_dir)
    print(" ✔ test_prompt_context_formatting: PASS")

    test_parse_invalid_pdf()
    print(" ✔ test_parse_invalid_pdf: PASS")

    print("\nTODOS OS 6 TESTES DE MULTIMODALIDADE FORAM APROVADOS COM SUCESSO!")
