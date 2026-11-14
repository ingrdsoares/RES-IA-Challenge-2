from app.guardrails import e_recusa, pede_dados


def test_recusa_curta_vira_recusa():
    assert e_recusa("Os documentos fornecidos não tratam do IPVA em Goiás. Portanto, não é possível determinar a alíquota.")


def test_recusa_sem_frase_final():
    assert e_recusa("Os documentos fornecidos não tratam do Imposto sobre Grandes Fortunas.")


def test_resposta_com_fonte_nao_e_recusa():
    assert not e_recusa("A multa do FGTS é de 40% do montante depositado, conforme o art. 10 do ADCT.")
    longa = "Os documentos tratam do tema. " * 30 + "Não é possível determinar o resto."
    assert not e_recusa(longa)


def test_pedido_de_dados():
    assert pede_dados("A resposta depende do regime, que você não informou. Por favor, forneça esses dados.")
    assert not pede_dados("O limite do MEI é de R$ 81 mil por ano.")
