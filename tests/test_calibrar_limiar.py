from scripts.calibrar_limiar import _verificar, calcular


def test_calculo_com_scores_falsos():
    _verificar()


def test_sem_limiar_valido():
    casos = [{"comportamento": "answer", "tem_fonte": True, "top_score": 0.3}]
    r = calcular(casos, [0.4, 0.5])
    assert r["recomendado"] is None and r["empate"] == []
