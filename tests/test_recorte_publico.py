import csv
import gzip
import json

import pytest
from app.config import Settings
from app.vector_store import VectorStore
from qdrant_client import QdrantClient

from src.rag.csv_para_qdrant import ingerir
from src.rag.recorte_csv import CsvAcimaDoTeto, gerar_recorte, regra_conteudo
from tests.test_recorte_rag import montar_run

COLECAO = "teste_publico"


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("**INTERESSADO : EMPRESA FICTICIA EXEMPLO LTDA.**", "parte"),
        ("| **INTERESSADO:** | **COMERCIO FICTICIO EXEMPLO LTDA** |", "parte"),
        ("Advogado: Dr. João da Silva", "parte"),
        ("Contribuinte:____________", None),
        ("| Razão Social: | ________ |", None),
        ("CPF 123.456.789-00", None),
        ("CPF 111.111.111-11", None),
        ("CPF 999.999.999-99", None),
        ("CPF ***.113.537-**", None),
        ("CPF 321.654.987-00", "cpf"),
        ("CPF 12345678975", "cpf"),
        ("CNPJ 00.000.000/0000-00", None),
        ("CNPJ 11.222.333/0001-81", "cnpj"),
        ("OAB/DF 00.111", "oab"),
        ("contato: fulano@gmail.com", "email"),
        ("contato: fiscal@fazenda.gov.br", None),
        ("contato: x@receita.fazenda.gov.br", None),
        ("Inscrição CF/DF nº 07.123.456-7", "cf_df"),
        ("Art. 1º A pessoa jurídica deverá recolher o imposto.", None),
        ("Consulente EMPRESA FICTICIA GLOBAL S.A. sobre ICMS", "razao_social"),
        ("Empresa EMPRESA FICTICIA EXEMPLO LTDA. consulta", "razao_social"),
        ("pela COMERCIO FICTICIO CELULOSE S/A, em", "razao_social"),
        ("Lei Complementar nº 123, Simples Nacional e MEI", None),
        ("Comércio de Produtos Hospitalares Ltda. sem caixa alta", None),
    ],
)
def test_regra_conteudo_com_formas_reais(texto, esperado):
    assert regra_conteudo("Título neutro", texto) == esperado


def test_titulo_tambem_e_verificado():
    assert regra_conteudo("Parecer de OAB/DF 00.111", "texto neutro") == "oab"


def _publico_run(tmp_path, specs):
    return montar_run(tmp_path / "run", specs)


@pytest.fixture
def run_publico(tmp_path):
    return _publico_run(
        tmp_path,
        [
            {
                "doc": "d-lei",
                "versao": "v-lei",
                "texto": "Art. 1º Lei.",
                "ocorrencias": [("nao_informada", "legislacao", "Lei 5.172/1966", "rfb:ato:5172")],
            },
            {
                "doc": "d-parte",
                "versao": "v-parte",
                "texto": "**INTERESSADO : EMPRESA FICTICIA EXEMPLO LTDA.**\n\nSolução de consulta.",
                "ocorrencias": [("consulta_tributaria", "consultas-rfb", "Consulta X", None)],
            },
            {
                "doc": "d-form",
                "versao": "v-form",
                "texto": "Contribuinte:______\n\nArt. 2º Modelo em branco.",
                "ocorrencias": [("manual", "manuais", "Formulário", None)],
            },
            {
                "doc": "d-cpf",
                "versao": "v-cpf",
                "texto": "Art. 1º CPF 321.654.987-00 aqui.",
                "ocorrencias": [("legislacao", "legislacao", "Lei CPF", None)],
            },
            {
                "doc": "d-juris",
                "versao": "v-juris",
                "texto": "Art. 1º Acórdão.",
                "ocorrencias": [
                    ("jurisprudencia_tarf", "documentos-jurisprudencia", "Acórdão Y", None)
                ],
            },
            {
                "doc": "d-diario",
                "versao": "v-diario",
                "texto": "Art. 1º Diário.",
                "ocorrencias": [
                    ("diario_com_consulta_tributaria", "consultas-rfb", "Diário Z", None)
                ],
            },
            {
                "doc": "d-gmail",
                "versao": "v-gm",
                "texto": "Art. 1º fulano@gmail.com",
                "ocorrencias": [("orientacao_oficial", "manuais", "Guia gmail", None)],
            },
            {
                "doc": "d-oab",
                "versao": "v-oab",
                "texto": "Art. 1º Peça.",
                "ocorrencias": [("legislacao", "legislacao", "Peça OAB/DF 00.111", None)],
            },
            {
                "doc": "d-natureza-titulo",
                "versao": "v-nt",
                "texto": "Art. 1º Neutro.",
                "ocorrencias": [("legislacao", "legislacao", "Lei da Silva 321.654.987-00", None)],
            },
        ],
    )


def test_publico_mantem_lei_e_forma_em_branco_e_exclui_o_resto(run_publico, tmp_path):
    saida = tmp_path / "out" / "recorte-publico.csv"
    gerar_recorte(run_publico, saida, publico=True)
    gz = saida.with_name("recorte-publico.csv.gz")
    assert gz.exists() and not saida.exists()
    with gzip.open(gz, "rt", encoding="utf-8", newline="") as f:
        linhas = {r["documento_id"]: r for r in csv.DictReader(f)}
    assert set(linhas) == {"d-lei", "d-form"}
    assert linhas["d-form"]["texto"] == "Contribuinte:______\n\nArt. 2º Modelo em branco."


def test_publico_manifesto_lista_regra_sem_valor_casado(run_publico, tmp_path):
    saida = tmp_path / "recorte-publico.csv"
    gerar_recorte(run_publico, saida, publico=True)
    texto = (tmp_path / "recorte-publico.manifesto.json").read_text(encoding="utf-8")
    manifesto = json.loads(texto)
    detalhe = {d["documento_id"]: d for d in manifesto["excluidos_detalhe"]}
    assert detalhe["d-parte"]["regra"] == "regra:parte"
    assert detalhe["d-cpf"]["regra"] == "regra:cpf"
    assert detalhe["d-gmail"]["regra"] == "regra:email"
    assert detalhe["d-oab"]["regra"] == "regra:oab"
    assert detalhe["d-juris"]["regra"] == "jurisprudencia_tarf"
    assert detalhe["d-diario"]["regra"] == "diario_com_consulta_tributaria"
    assert detalhe["d-natureza-titulo"]["regra"] == "regra:cpf"
    assert detalhe["d-cpf"]["titulo"] == "[omitido]"
    assert detalhe["d-juris"]["titulo"] == "Acórdão Y"
    assert detalhe["d-natureza-titulo"]["titulo"] == "[omitido]"
    for valor in [
        "321.654.987-00",
        "EMPRESA FICTICIA",
        "EXEMPLO",
        "fulano@",
        "00.111",
        "123.456.789-00",
    ]:
        assert valor not in texto


def test_publico_grava_gz_nivel_9_e_round_trip(run_publico, tmp_path):
    saida = tmp_path / "recorte-publico.csv"
    manifesto = gerar_recorte(run_publico, saida, publico=True)
    gz = tmp_path / "recorte-publico.csv.gz"
    assert manifesto["gz_bytes"] == gz.stat().st_size
    assert manifesto["gz"] == "recorte-publico.csv.gz"
    with gzip.open(gz, "rt", encoding="utf-8", newline="") as f:
        assert len(list(csv.reader(f))) == manifesto["linhas"] + 1


def test_publico_aborta_acima_do_teto_gz_sem_arquivos(run_publico, tmp_path):
    saida = tmp_path / "recorte-publico.csv"
    with pytest.raises(CsvAcimaDoTeto):
        gerar_recorte(run_publico, saida, publico=True, teto_gz_bytes=10)
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith("recorte-publico")] == []


def test_ingestao_le_csv_gz(run_publico, tmp_path):
    saida = tmp_path / "recorte-publico.csv"
    gerar_recorte(run_publico, saida, publico=True)
    settings = Settings()
    client = QdrantClient(":memory:")
    VectorStore(
        settings.model_copy(update={"collection_name": COLECAO}), client
    ).ensure_collection()

    def embed(textos):
        return [[1.0] + [0.0] * 1023 for _ in textos]

    stats = ingerir(
        tmp_path / "recorte-publico.csv.gz",
        settings=settings,
        client=client,
        embed=embed,
        colecao=COLECAO,
    )
    assert stats["documentos"] == 2


# --- rodada de privacidade: NBSP, CF/DF sem barra, CNPJ sem máscara, misto, dump, revisão manual
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("**INTERESSADO : EMPRESA FICTICIA**", "parte"),
        (" Advogado: Fulano de Tal", "parte"),
        ("Inscrição CF DF nº 07.123.456-7", "cf_df"),
        ("Inscrição CFDF 07.123.456-7", "cf_df"),
        ("CNPJ 11222333/0001-81", "cnpj"),
        ("CNPJ 11.222.333/00001-81", None),
        ("CNPJ 00000000/00001-00", None),
        ("CNPJ 00011122/0001-33", "cnpj"),
        ("Processo 00011122333/2016-11", None),
        ("Ato 12345678/2019-40", None),
        ("Candidato Média 12 e Candidato Media 13", "dump_dou"),
        ("Candidato Média", "dump_dou"),
    ],
)
def test_regras_de_privacidade_novas(texto, esperado):
    assert regra_conteudo("Título neutro", texto) == esperado


@pytest.mark.parametrize(
    "natureza, texto, esperado",
    [
        (
            "consulta_tributaria",
            "Empresa Comercio Modelo do Brasil S/A consulta",
            "razao_social_misto",
        ),
        (
            "interpretacao_administrativa",
            "Empresa Exemplo Solucoes Ltda. pede",
            "razao_social_misto",
        ),
        ("legislacao", "Empresa Comercio Modelo do Brasil S/A consulta", None),
        ("consulta_tributaria", "Comercio Exemplo ME apresenta consulta", None),
        (
            "consulta_tributaria",
            "da sociedade fictícia Ltda. pede orientação",
            "razao_social_misto",
        ),
        ("interpretacao_administrativa", "a empresa exemplo LTDA consultou", "razao_social_misto"),
        ("consulta_tributaria", "a sociedade exemplo ltda consultou", None),
        ("legislacao", "da sociedade fictícia Ltda. pede orientação", None),
    ],
)
def test_razao_social_misto_so_em_consultas(natureza, texto, esperado):
    assert regra_conteudo("Título neutro", texto, natureza=natureza) == esperado


def test_revisao_manual_vem_de_lista_versionada_e_exclui(run_publico, tmp_path):
    from src.rag.recorte_csv import REVISAO_MANUAL_PATH

    ids = json.loads(REVISAO_MANUAL_PATH.read_text(encoding="utf-8"))
    assert len(ids) == 4 and all(len(i) == 64 for i in ids)
    saida = tmp_path / "recorte-publico.csv"
    gerar_recorte(run_publico, saida, publico=True, revisao_manual=frozenset({"d-lei"}))
    m = json.loads((tmp_path / "recorte-publico.manifesto.json").read_text(encoding="utf-8"))
    detalhe = {d["documento_id"]: d for d in m["excluidos_detalhe"]}
    assert detalhe["d-lei"]["regra"] == "revisao_manual"
