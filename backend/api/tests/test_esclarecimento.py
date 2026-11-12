import pytest
from app.esclarecimento import pedir_esclarecimento


@pytest.mark.parametrize(
    "pergunta, trecho",
    [
        ("Minha empresa pode entrar no Simples?", "CNAE"),
        (
            "Minha empresa de tecnologia presta serviços e quero saber em qual anexo do Simples vou pagar o imposto.",
            "folha",
        ),
        ("Quanto vou pagar de imposto este mês?", "regime"),
        ("Atrasei minha declaração. Vou pagar multa?", "declaração"),
        ("Estou atrasado com a guia. Quanto pago de juros?", "guia"),
        ("Quanto de ISS eu pago?", "município"),
        ("Preciso reter ISS dessa nota?", "tomador"),
    ],
)
def test_pede_dados_quando_faltam(pergunta, trecho):
    assert trecho in pedir_esclarecimento(pergunta)


@pytest.mark.parametrize(
    "pergunta",
    [
        "Qual o limite do MEI?",
        "Até quanto uma ME pode faturar?",
        "Uma empresa pode entrar no Simples?",
        "Minha empresa fatura R$ 200 mil por ano e pode entrar no Simples?",
        "Minha empresa tem CNAE 6201-5/01, RBT12 de 500000 e folha de 100000. Qual anexo?",
        "Qual anexo do Simples se aplica a uma empresa de TI?",
        "Qual a multa por atraso na entrega da declaração?",
        "Como são calculados os juros sobre tributos em atraso?",
        "Atrasei a DAS de março de 2024, de R$ 500. Quanto pago de juros?",
        "Atrasei a declaração de 2023 do Simples. Vou pagar multa?",
        "Qual a alíquota de ISS?",
        "Quanto de ISS eu pago em São Paulo sobre R$ 10.000 de serviço?",
        "Quando o tomador deve reter ISS?",
        "Preciso reter ISS dessa nota de R$ 3.000 em Curitiba?",
    ],
)
def test_nao_dispara_em_pergunta_geral_ou_completa(pergunta):
    assert pedir_esclarecimento(pergunta) is None
