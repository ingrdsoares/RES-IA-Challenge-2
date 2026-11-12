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
    ],
)
def test_nao_dispara_em_pergunta_geral_ou_completa(pergunta):
    assert pedir_esclarecimento(pergunta) is None
