from types import SimpleNamespace

import pytest
from app.config import Settings
from app.ferramentas import MAX_CHAMADAS, PlanejadorBuscas, intercalar, validar
from app.rag import RagService
from app.schemas import Source


def fonte(texto, titulo="Doc"):
    return Source(id=texto, text=texto, source="Fonte", title=titulo, score=0.8)


def resposta(*chamadas):
    tool_calls = [
        SimpleNamespace(function=SimpleNamespace(name=n, arguments=a)) for n, a in chamadas
    ]
    return SimpleNamespace(message=SimpleNamespace(tool_calls=tool_calls or None, content=""))


@pytest.mark.parametrize(
    ("nome", "args", "pergunta", "vistos", "trecho"),
    [
        ("apagar", {}, "x", "", "desconhecida"),
        ("busca_geral", "texto", "x", "", "inválidos"),
        ("busca_geral", {}, "x", "", "consulta"),
        ("buscar_norma", {"norma": "LC 87", "consulta": "x"}, "Qual o ICMS?", "", "fora da"),
        ("buscar_norma", {"norma": "qualquer", "consulta": "x"}, "LC 87?", "", "reconhecida"),
        ("buscar_artigo", {"norma": "LC 87", "artigo": "23"}, "O que diz a LC 87?", "", "fora da"),
        ("buscar_artigo", {"norma": "LC 87", "artigo": "abc"}, "LC 87?", "", "inválido"),
    ],
)
def test_rejeicoes(nome, args, pergunta, vistos, trecho):
    assert trecho in validar(nome, args, pergunta, vistos)


@pytest.mark.parametrize(
    ("nome", "args", "pergunta", "vistos"),
    [
        ("busca_geral", {"consulta": "limite do MEI"}, "Qual o limite?", ""),
        ("buscar_norma", {"norma": "LC 87", "consulta": "base"}, "Pela Lei Kandir?", ""),
        ("buscar_norma", {"norma": "Lei 1.254", "consulta": "alíquota"}, "ICMS?", "Lei nº 1.254"),
        ("buscar_artigo", {"norma": "LC 87", "artigo": "23"}, "O art. 23 da LC 87?", ""),
        ("buscar_artigo", {"norma": "LC 123", "artigo": "13-A"}, "ICMS?", "art. 13-A da LC 123"),
    ],
)
def test_aceita_o_que_vem_da_pergunta_ou_de_resultado(nome, args, pergunta, vistos):
    assert validar(nome, args, pergunta, vistos) is None


def test_laco_devolve_erro_ao_modelo_bloqueia_repeticao_e_para_sem_chamadas():
    roteiro = iter(
        [
            resposta(("buscar_artigo", {"norma": "LC 87", "artigo": "999"})),
            resposta(
                ("busca_geral", {"consulta": "a"}),
                ("busca_geral", {"consulta": "a"}),
            ),
            resposta(),
        ]
    )
    mensagens_vistas = []

    def chat(mensagens, ferramentas):
        mensagens_vistas.append(list(mensagens))
        return next(roteiro)

    executadas = []

    def executar(nome, args):
        executadas.append((nome, args))
        return [fonte("trecho a")]

    coleta = PlanejadorBuscas(chat, executar).coletar("O que diz a LC 87?")

    assert executadas == [("busca_geral", {"consulta": "a"})]
    assert [r["erro"] is None for r in coleta.registro] == [False, True, False]
    assert "Erro:" in mensagens_vistas[1][-1]["content"]


def test_limite_de_chamadas_encerra():
    def chat(mensagens, ferramentas):
        n = len(mensagens)
        return resposta(*[("busca_geral", {"consulta": f"c{n}-{i}"}) for i in range(4)])

    coleta = PlanejadorBuscas(chat, lambda n, a: [fonte("t")]).coletar("x")

    assert len(coleta.grupos) == MAX_CHAMADAS


def test_intercalar_alterna_as_buscas():
    a, b, c = fonte("a"), fonte("b"), fonte("c")
    assert intercalar([[a, c], [b]]) == [a, b, c]
    assert intercalar([]) == []


class Store:
    def __init__(self):
        self.gerais = []

    def ensure_collection(self):
        pass

    def count(self):
        return 1

    def search_norms(self, vetor, chaves):
        return [], []

    def search_articles(self, vetor, pares):
        return []

    def search(self, vetor, pergunta):
        self.gerais.append(pergunta)
        return [fonte(f"achado {pergunta}")]

    def close(self):
        pass


class Modelos:
    def __init__(self, chat):
        self.planejar = chat
        self.fontes = None

    def embed_question(self, pergunta):
        return [1.0]

    def answer(self, pergunta, fontes, ausentes):
        self.fontes = fontes
        return "Resposta [1]"

    def close(self):
        pass


def test_servico_usa_uma_busca_por_parte_da_pergunta():
    roteiro = iter(
        [
            resposta(("busca_geral", {"consulta": "base"}), ("busca_geral", {"consulta": "taxa"})),
            resposta(),
        ]
    )
    store = Store()
    modelos = Modelos(lambda m, f: next(roteiro))
    servico = RagService(Settings(reranker_url=None, tool_calling=True), store, modelos)

    servico.query("Qual a base e a taxa?")

    assert store.gerais == ["base", "taxa"]
    assert [f.text for f in modelos.fontes] == ["achado base", "achado taxa"]


def test_falha_no_planejamento_cai_na_busca_atual():
    def quebra(mensagens, ferramentas):
        raise RuntimeError("modelo fora")

    store = Store()
    modelos = Modelos(quebra)
    servico = RagService(Settings(reranker_url=None, tool_calling=True), store, modelos)

    resposta_final = servico.query("Qual a base?")

    assert resposta_final.status == "answered"
    assert store.gerais == ["Qual a base?"]


def test_sem_chamadas_usa_a_busca_atual_e_desligado_nao_planeja():
    store = Store()
    modelos = Modelos(lambda m, f: resposta())
    RagService(Settings(reranker_url=None, tool_calling=True), store, modelos).query("Oi?")
    assert store.gerais == ["Oi?"]

    def nao_chamar(mensagens, ferramentas):
        raise AssertionError("não deveria planejar")

    store = Store()
    RagService(Settings(reranker_url=None), store, Modelos(nao_chamar)).query("Oi?")
    assert store.gerais == ["Oi?"]
