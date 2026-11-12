import pytest
from app.compostas import consultas_de_busca, partes_da_pergunta
from app.config import Settings
from app.rag import RagService
from app.schemas import Source


@pytest.mark.parametrize(
    ("pergunta", "esperado"),
    [
        (
            "Qual é a alíquota mínima do ISS e qual é a máxima?",
            ["Qual é a alíquota mínima do ISS", "qual é a máxima"],
        ),
        (
            "O ICMS incide sobre livros? E sobre a exportação de mercadorias?",
            ["O ICMS incide sobre livros", "E sobre a exportação de mercadorias"],
        ),
        (
            "Qual o limite do MEI e o que acontece se ultrapassar?",
            ["Qual o limite do MEI", "o que acontece se ultrapassar"],
        ),
        (
            "Sobre o ICMS: quem é contribuinte, e quando ele incide?",
            ["Sobre o ICMS: quem é contribuinte", "Sobre o ICMS: quando ele incide"],
        ),
        ("Quais obrigações a ME e a EPP têm?", ["Quais obrigações a ME e a EPP têm?"]),
        ("Qual é o limite de receita do MEI?", ["Qual é o limite de receita do MEI?"]),
        ("Qual é o prazo e o valor?", ["Qual é o prazo e o valor?"]),
        (
            "Qual é o limite de receita do MEI e ele pode emitir a NFS-e de padrão nacional em "
            "operação só de ICMS?",
            [
                "Qual é o limite de receita do MEI",
                "ele pode emitir a NFS-e de padrão nacional em operação só de ICMS",
            ],
        ),
        (
            "Qual o limite do MEI, e precisa declarar o faturamento?",
            ["Qual o limite do MEI", "precisa declarar o faturamento"],
        ),
        (
            "O MEI paga DAS e também deve recolher ISS?",
            ["O MEI paga DAS", "também deve recolher ISS"],
        ),
        ("Qual a diferença entre Simples e Lucro Presumido?", None),
        ("O MEI pode emitir NF-e e NFS-e?", None),
        ("Como o ICMS e o ISS incidem sobre receita e despesa?", None),
        ("Quais obrigações a ME e a EPP têm?", None),
    ],
)
def test_partes_da_pergunta(pergunta, esperado):
    assert partes_da_pergunta(pergunta) == (esperado or [pergunta])


def test_parte_curta_herda_o_assunto_da_primeira():
    consultas = consultas_de_busca(["Qual é a alíquota mínima do ISS", "qual é a máxima"])
    assert consultas == [
        "Qual é a alíquota mínima do ISS",
        "qual é a máxima ISS a aliquota minima do iss",
    ]


def test_parte_sem_interrogativa_carrega_o_assunto_do_mei():
    partes = ["Qual é o limite de receita do MEI", "ele pode emitir NFS-e"]
    assert consultas_de_busca(partes)[1] == "ele pode emitir NFS-e o limite de receita do mei"


def test_parte_sem_sigla_herda_as_anteriores_e_parte_com_sigla_fica_como_esta():
    sem_sigla = ["Qual é o fato gerador do ISS", "qual é a sua base de cálculo segundo a lei"]
    assert consultas_de_busca(sem_sigla)[1] == "qual é a sua base de cálculo segundo a lei ISS"
    com_sigla = ["Qual é o limite da EPP no ano", "qual é o limite para recolher ICMS e ISS"]
    assert consultas_de_busca(com_sigla) == com_sigla


def test_limite_de_partes():
    pergunta = "Qual é A1 B1? Qual é A2 B2? Qual é A3 B3? Qual é A4 B4?"
    assert len(partes_da_pergunta(pergunta)) == 3


def fonte(texto):
    return Source(id=texto, text=texto, source="Fonte", score=0.8)


class Store:
    def __init__(self):
        self.consultas = []

    def ensure_collection(self):
        pass

    def count(self):
        return 1

    def search_norms(self, vetor, chaves):
        return [], []

    def search_articles(self, vetor, pares):
        return []

    def search(self, vetor, pergunta):
        self.consultas.append(pergunta)
        return [fonte(f"{pergunta} 1"), fonte(f"{pergunta} 2")]

    def close(self):
        pass


class Modelos:
    def __init__(self):
        self.fontes = None

    def embed_question(self, pergunta):
        return [1.0]

    def answer(self, pergunta, fontes, ausentes):
        self.fontes = fontes
        return "Resposta [1]"

    def close(self):
        pass


def test_servico_busca_cada_parte_e_alterna_os_trechos():
    store, modelos = Store(), Modelos()
    RagService(Settings(reranker_url=None), store, modelos).query(
        "Qual é a base de cálculo do ISS? E qual é o prazo do DAS do MEI?"
    )
    assert store.consultas == [
        "Qual é a base de cálculo do ISS? E qual é o prazo do DAS do MEI?",
        "Qual é a base de cálculo do ISS",
        "E qual é o prazo do DAS do MEI",
    ]
    inteira = "Qual é a base de cálculo do ISS? E qual é o prazo do DAS do MEI?"
    assert [f.text for f in modelos.fontes][:6] == [
        f"{inteira} 1",
        f"{inteira} 2",
        "Qual é a base de cálculo do ISS 1",
        "E qual é o prazo do DAS do MEI 1",
        "Qual é a base de cálculo do ISS 2",
        "E qual é o prazo do DAS do MEI 2",
    ]


def test_pergunta_simples_continua_com_uma_busca():
    store = Store()
    RagService(Settings(reranker_url=None), store, Modelos()).query("Qual é a base do ISS?")
    assert store.consultas == ["Qual é a base do ISS?"]
