import json
from pathlib import Path

from app.sinonimos import expandir_consulta
from app.sparse import PESO_EXPANSAO, _indice, vetor_consulta


def test_sigla_expande():
    assert "documento de arrecadação" in expandir_consulta("Quando vence o DAS?")
    assert "receita bruta acumulada" in expandir_consulta("Como calculo a RBT12?")
    assert "microempreendedor individual" in expandir_consulta("limite do MEI")


def test_termo_coloquial_e_inverso():
    assert "receita bruta" in expandir_consulta("Qual o limite de faturamento?")
    assert "das" in expandir_consulta("documento de arrecadação do Simples Nacional")
    assert "pessoa jurídica" in expandir_consulta("pejotização é legal?")


def test_nao_confunde_palavras_comuns():
    assert expandir_consulta("Quero ir ao banco, me diga como fazer") == ""
    assert expandir_consulta("o imposto pode ser pago em dinheiro") == ""
    assert expandir_consulta("Das 10 maneiras, a das flores") == ""  # "das" minúsculo não é DAS


def test_peso_menor_para_expansao():
    idx, val = vetor_consulta("limite do MEI")
    pesos = dict(zip(idx, val))
    assert pesos[_indice("mei")] == 1.0
    assert pesos[_indice("microempreendedor")] == PESO_EXPANSAO


def test_termo_original_nao_rebaixado():
    idx, val = vetor_consulta("receita bruta e faturamento")
    assert dict(zip(idx, val))[_indice("receita")] == 1.0


def test_sem_expansao_igual_ao_anterior():
    idx, val = vetor_consulta("prazo de recolhimento")
    assert set(val) == {1.0}


def test_estatisticas_datasets():
    dados = Path(__file__).parents[2] / "evaluation" / "data"
    perguntas = [
        json.loads(linha)["question"]
        for f in dados.glob("*.jsonl")
        for linha in f.open(encoding="utf8")
        if linha.strip()
    ]
    expandidas = [q for q in perguntas if expandir_consulta(q)]
    assert perguntas and len(expandidas) < len(perguntas)
