from app.citacoes_normas import avisar_sem_suporte, pares_fontes, sem_suporte
from app.schemas import Source

FONTE = {
    "text": "Art. 18-A. O MEI pode optar pelo Simples.",
    "title": "Lei Complementar nº 123/2006",
    "source": "lc123.pdf",
}


def test_abreviacao_e_nome_por_extenso_casam():
    assert sem_suporte("Veja o art. 18-A da LC 123.", [FONTE]) == []
    assert sem_suporte("Conforme o artigo 18-A da Lei Complementar nº 123/2006.", [FONTE]) == []


def test_artigo_ou_norma_diferente_sem_suporte():
    assert sem_suporte("O art. 19 da LC 123 limita.", [FONTE]) == [("lc:123", "19")]
    assert sem_suporte("O art. 18-A da Lei 9.999 diz.", [FONTE]) == [("lei:9999", "18-a")]


def test_artigo_so_no_texto_vizinho_conta():
    fonte = {"text": "Art. 17. Vedações.\n\nArt. 18. Alíquotas.", "title": "LC 123", "source": "x"}
    assert sem_suporte("O art. 18 da LC 123.", [fonte]) == []


def test_aceita_source_do_pydantic():
    s = Source(id=1, text=FONTE["text"], source="lc123.pdf", score=1.0, title=FONTE["title"])
    assert ("lc:123", "18-a") in pares_fontes([s])


def test_sem_citacao_nao_altera():
    assert avisar_sem_suporte("Resposta [1].", [FONTE]) == ("Resposta [1].", [])


def test_aviso_lista_referencias_e_preserva_corpo():
    resposta = "O art. 19 da LC 123 limita e o art. 18-A da LC 123 permite."
    texto, faltam = avisar_sem_suporte(resposta, [FONTE])
    assert texto.startswith(resposta)
    assert faltam == [("lc:123", "19")]
    assert "art. 19 da Lei Complementar 123" in texto
    assert "18-A da" not in texto.removeprefix(resposta)
