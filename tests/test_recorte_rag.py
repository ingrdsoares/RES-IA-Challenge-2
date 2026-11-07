import csv
import hashlib
import json
from pathlib import Path

import pytest
from app.config import Settings
from app.errors import DependencyUnavailable
from app.schemas import Source
from app.vector_store import VectorStore
from qdrant_client import QdrantClient

from src.rag.csv_para_qdrant import (
    LIMITE_CORPO,
    com_retentativas,
    estatisticas_novas,
    ingerir,
    itens_do_documento,
    ler_csv,
    partir_corpo,
    ponto_id,
)
from src.rag.csv_para_qdrant import (
    main as main_ponte,
)
from src.rag.recorte_csv import (
    COLUNAS,
    NATUREZAS_PERMITIDAS,
    CsvAcimaDoTeto,
    gerar_recorte,
)

TEXTO_A = 'Art. 1º Texto com "aspas", vírgula;\nlinha ~~rasura~~ e =SOMA(A1)\n\nArt. 2º Segundo.'
TEXTO_D = "Art. 1º Orientação oficial curta."
COLECAO = "teste_recorte"


def _escrever_jsonl(caminho: Path, registros: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def montar_run(base: Path, specs: list[dict]) -> Path:
    """Cria um run do refino a partir de especificações.

    spec: doc, versao, texto, ocorrencias=[(natureza, frente, titulo, chave_origem|None)],
    preferida (default True). Só a versão preferida entra em indice_nucleo.jsonl.
    """
    ocorrencias, versoes, documentos, nucleo = [], [], {}, []
    for spec in specs:
        doc, versao = spec["doc"], spec["versao"]
        ids = []
        for k, (natureza, frente, titulo, chave) in enumerate(spec["ocorrencias"]):
            oid = f"oc-{versao}-{k}"
            ids.append(oid)
            ocorrencias.append(
                {
                    "id": oid,
                    "versao_id": versao,
                    "documento_id": doc,
                    "conteudo_id": f"c-{versao}",
                    "natureza": natureza,
                    "frente": frente,
                    "classificacao": "nucleo",
                    "source_url": f"https://fonte.test/{oid}",
                    "titulo": titulo,
                    "coletado_em": "2026-11-04T10:00:00+00:00",
                    "chave_origem": chave or f"url:{oid}",
                    "vigencia": "nao_verificada",
                    "bytes_texto": 10,
                }
            )
        versoes.append(
            {"id": versao, "documento_id": doc, "conteudo_id": f"c-{versao}", "ocorrencias": ids}
        )
        (base / "conteudos").mkdir(parents=True, exist_ok=True)
        (base / "conteudos" / f"c-{versao}.md").write_bytes(spec["texto"].encode("utf-8"))
        d = documentos.setdefault(
            doc,
            {
                "id": doc,
                "naturezas": [],
                "chave_origem": f"url:{doc}",
                "titulos": [o[2] for o in spec["ocorrencias"]],
                "representacao_preferida": None,
                "versoes": [],
                "ocorrencias": [],
                "categorias": ["nucleo"],
                "criterio_representacao": "x",
            },
        )
        d["versoes"].append(versao)
        d["ocorrencias"] += ids
        d["naturezas"] += [o[0] for o in spec["ocorrencias"]]
        if spec.get("preferida", True):
            d["representacao_preferida"] = versao
    for d in documentos.values():
        if d["representacao_preferida"]:
            nucleo.append(
                {
                    "documento_id": d["id"],
                    "representacao_preferida": d["representacao_preferida"],
                    "revisao_semantica": "pendente",
                    "titulos": d["titulos"],
                    "versoes": d["versoes"],
                }
            )
    _escrever_jsonl(base / "ocorrencias.jsonl", ocorrencias)
    _escrever_jsonl(base / "versoes.jsonl", versoes)
    _escrever_jsonl(base / "documentos.jsonl", list(documentos.values()))
    _escrever_jsonl(base / "indice_nucleo.jsonl", nucleo)
    return base


@pytest.fixture
def run(tmp_path):
    """A: legislacao + versão não preferida; B: nao_informada sem ato; C: cnpj; D: orientacao."""
    return montar_run(
        tmp_path / "run",
        [
            {
                "doc": "doc-a",
                "versao": "ver-a1",
                "texto": TEXTO_A,
                "ocorrencias": [("legislacao", "legislacao", "Lei A", None)],
            },
            {
                "doc": "doc-a",
                "versao": "ver-a2",
                "preferida": False,
                "texto": "Art. 1º versão antiga.",
                "ocorrencias": [("legislacao", "legislacao", "Lei A antiga", None)],
            },
            {
                "doc": "doc-b",
                "versao": "ver-b",
                "texto": "Art. 1º B.",
                "ocorrencias": [("nao_informada", "legislacao", "Ato B", None)],
            },
            {
                "doc": "doc-c",
                "versao": "ver-c",
                "texto": "Art. 1º C.",
                "ocorrencias": [("legislacao", "cnpj-df", "Dado C", None)],
            },
            {
                "doc": "doc-d",
                "versao": "ver-d",
                "texto": TEXTO_D,
                "ocorrencias": [("orientacao_oficial", "manuais", "Guia D", None)],
            },
        ],
    )


def _linhas(saida: Path) -> dict[str, dict]:
    with open(saida, encoding="utf-8", newline="") as f:
        return {r["documento_id"]: r for r in csv.DictReader(f)}


def test_csv_ida_e_volta_preserva_texto_e_colunas(run, tmp_path):
    saida = tmp_path / "out" / "recorte.csv"
    gerar_recorte(run, saida)
    with open(saida, encoding="utf-8", newline="") as f:
        assert csv.DictReader(f).fieldnames == list(COLUNAS)
    linhas = _linhas(saida)
    assert set(linhas) == {"doc-a", "doc-d"}
    assert linhas["doc-a"]["texto"] == TEXTO_A
    assert linhas["doc-a"]["versao_id"] == "ver-a1"
    assert linhas["doc-a"]["source_url"] == "https://fonte.test/oc-ver-a1-0"
    assert linhas["doc-a"]["vigencia_fonte"] == ""


def test_allowlist_exclui_natureza_fora_e_cnpj(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    manifesto = gerar_recorte(run, saida)
    assert "nao_informada" not in NATUREZAS_PERMITIDAS
    assert manifesto["excluidos"]["nao_informada"]["documentos"] == 1
    assert manifesto["excluidos"]["nao_informada"]["bytes_texto"] == len("Art. 1º B.".encode())
    assert manifesto["excluidos"]["frente_cnpj"]["documentos"] == 1
    assert manifesto["contagens_por_natureza"] == {"legislacao": 1, "orientacao_oficial": 1}


def test_allowlist_inclui_naturezas_de_nucleo_tributario():
    esperadas = {
        "consulta_acordao_administrativo",
        "diario_com_consulta_tributaria",
        "diario_com_jurisprudencia_tributaria",
        "informativo_jurisprudencial",
        "perguntas_respostas",
        "orientacao_mei",
        "manual",
        "documentacao_classificacao_oficial",
    }
    assert esperadas <= NATUREZAS_PERMITIDAS
    for fora in ["agenda_diaria", "agenda_mes", "pdf", "documentacao_tecnica", "norma_contabil"]:
        assert fora not in NATUREZAS_PERMITIDAS


@pytest.fixture
def run_atos(tmp_path):
    return montar_run(
        tmp_path / "run_atos",
        [
            {
                "doc": "doc-lei",
                "versao": "v-lei",
                "texto": "Art. 1º Lei.",
                "ocorrencias": [("nao_informada", "legislacao", "Lei 5.172/1966", "rfb:ato:5172")],
            },
            {
                "doc": "doc-df",
                "versao": "v-df",
                "texto": "Art. 1º DF.",
                "ocorrencias": [("pagina_oficial", "distrital-df", "Página DF", "df-lei-963")],
            },
            {
                "doc": "doc-cnpj",
                "versao": "v-cnpj",
                "texto": "cnpj.",
                "ocorrencias": [("nao_informada", "legislacao", "cnpj_df", "cnpj_df:agenda")],
            },
            {
                "doc": "doc-agenda",
                "versao": "v-ag",
                "texto": "agenda.",
                "ocorrencias": [
                    ("pagina_oficial", "calendario-df", "Agenda tributária", "url:agenda")
                ],
            },
            {
                "doc": "doc-misto",
                "versao": "v-misto",
                "texto": "Art. 1º misto.",
                "ocorrencias": [
                    ("legislacao", "legislacao", "Lei X", None),
                    ("nao_informada", "legislacao", "Lei X2", "url:x2"),
                ],
            },
            {
                "doc": "doc-misto2",
                "versao": "v-misto2",
                "texto": "Art. 1º misto2.",
                "ocorrencias": [
                    ("legislacao", "legislacao", "Lei Y", None),
                    ("nao_informada", "legislacao", "Ato Y", None),
                ],
            },
            {
                "doc": "doc-dominio",
                "versao": "v-dom",
                "texto": "Página do portal.",
                "ocorrencias": [
                    ("pagina_oficial", "x", "Página do portal", "url:https://www.in.gov.br/home"),
                ],
            },
            {
                "doc": "doc-manual",
                "versao": "v-man",
                "texto": "Manual.",
                "ocorrencias": [("manual", "manuais", "Manual X", None)],
            },
            {
                "doc": "doc-pdf",
                "versao": "v-pdf",
                "texto": "pdf.",
                "ocorrencias": [("pdf", "manuais", "Arquivo", None)],
            },
        ],
    )


def test_nao_informada_e_pagina_entram_so_com_ato_legal(run_atos, tmp_path):
    saida = tmp_path / "atos.csv"
    manifesto = gerar_recorte(run_atos, saida)
    incluidos = set(_linhas(saida))
    assert incluidos == {"doc-lei", "doc-df", "doc-misto", "doc-manual"}
    assert manifesto["excluidos"]["nao_informada"]["documentos"] == 2  # cnpj_df e Ato Y
    assert manifesto["excluidos"]["pagina_oficial"]["documentos"] == 2  # agenda e in.gov.br
    assert manifesto["excluidos"]["pdf"]["documentos"] == 1
    titulos = {c["titulo"] for c in manifesto["condicionais_excluidos"]}
    assert {"cnpj_df", "Agenda tributária"} <= titulos
    assert not ({"Lei 5.172/1966", "Página DF"} & titulos)


def test_misto_entra_so_se_todas_as_naturezas_permitidas(run_atos, tmp_path):
    saida = tmp_path / "atos.csv"
    gerar_recorte(run_atos, saida)
    assert "doc-misto2" not in _linhas(saida)


def test_aborta_acima_do_teto_sem_deixar_arquivo(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    with pytest.raises(CsvAcimaDoTeto):
        gerar_recorte(run, saida, teto_bytes=50)
    assert not saida.exists()
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith("recorte")] == []


def test_manifesto_traz_sha256_e_bytes_do_csv(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    manifesto = json.loads((tmp_path / "recorte.csv.manifesto.json").read_text(encoding="utf-8"))
    dados = saida.read_bytes()
    assert manifesto["bytes"] == len(dados)
    assert manifesto["sha256"] == hashlib.sha256(dados).hexdigest()
    assert manifesto["linhas"] == 2


class _EmbedFalso:
    """Vetores de dimensão 1024 sem modelo; guarda os textos recebidos."""

    def __init__(self):
        self.chamadas = 0
        self.textos: list[str] = []

    def __call__(self, textos):
        self.chamadas += 1
        self.textos += textos
        return [[1.0 if i == j % 1024 else 0.0 for j in range(1024)] for i, _ in enumerate(textos)]


def _memoria(settings):
    client = QdrantClient(":memory:")
    VectorStore(
        settings.model_copy(update={"collection_name": COLECAO}), client
    ).ensure_collection()
    return client


def _pontos(client):
    pontos, _ = client.scroll(COLECAO, limit=10_000, with_payload=True)
    return pontos


def test_ponte_dry_run_nao_chama_modelo_nem_qdrant(run, tmp_path, capsys):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    embed = _EmbedFalso()
    main_ponte(["--csv", str(saida), "--dry-run"], embed=embed, client=None)
    assert embed.chamadas == 0
    assert "documentos: 2" in capsys.readouterr().out


def test_gravacao_exige_colecao_explicita(run, tmp_path, capsys):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    with pytest.raises(SystemExit):
        main_ponte(["--csv", str(saida)], embed=_EmbedFalso(), client=QdrantClient(":memory:"))
    # dry-run não precisa de coleção
    main_ponte(["--csv", str(saida), "--dry-run"], embed=_EmbedFalso(), client=None)


def test_upsert_reexecucao_nao_duplica_e_payload_valida_em_source(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    settings = Settings()
    client = _memoria(settings)
    embed = _EmbedFalso()
    ingerir(saida, settings=settings, client=client, embed=embed, colecao=COLECAO)
    total = client.count(COLECAO, exact=True).count
    assert total >= 2
    ingerir(saida, settings=settings, client=client, embed=embed, colecao=COLECAO)
    assert client.count(COLECAO, exact=True).count == total
    for ponto in _pontos(client):
        fonte = Source.model_validate(ponto.payload | {"id": ponto.id, "score": 0.0})
        assert fonte.source.startswith("https://fonte.test/")
        assert fonte.effective_date is None
    assert {p.payload["document_id"] for p in _pontos(client)} == {"doc-a", "doc-d"}


def test_limite_processa_so_as_primeiras_linhas(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    settings = Settings()
    client = _memoria(settings)
    ingerir(saida, settings=settings, client=client, embed=_EmbedFalso(), colecao=COLECAO, limite=1)
    assert {p.payload["document_id"] for p in _pontos(client)} == {"doc-a"}


def test_reexportacao_com_novo_versao_remove_pontos_antigos(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    settings = Settings()
    client = _memoria(settings)
    ingerir(saida, settings=settings, client=client, embed=_EmbedFalso(), colecao=COLECAO)
    # mesma linha de doc-a, com outra versao_id (re-exportação após nova versão)
    linhas = list(ler_csv(saida))
    nova = tmp_path / "nova.csv"
    with open(nova, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(COLUNAS))
        escritor.writeheader()
        for linha in linhas:
            if linha["documento_id"] == "doc-a":
                linha = linha | {"versao_id": "ver-a-nova"}
            escritor.writerow(linha)
    ingerir(nova, settings=settings, client=client, embed=_EmbedFalso(), colecao=COLECAO)
    pontos_a = [p for p in _pontos(client) if p.payload["document_id"] == "doc-a"]
    novos = {ponto_id("ver-a-nova", i) for i in range(len(pontos_a))}
    assert {p.id for p in pontos_a} == novos


def test_ler_csv_aceita_campo_grande(tmp_path):
    caminho = tmp_path / "grande.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(COLUNAS)
        escritor.writerow(["d", "v", "t", "n", "f", "c", "u", "e", "", "x" * 300_000])
    assert len(list(ler_csv(caminho))[0]["texto"]) == 300_000


def test_corpo_gigante_gera_so_partes_pequenas_sem_perda(tmp_path):
    corpo = " ".join(f"w{i}" for i in range(120_000))[:772_428]
    palavras = corpo.split()[:-1]  # a última pode ter sido cortada pelo recorte
    texto = "Art. 1º " + corpo
    base = montar_run(
        tmp_path / "gigante",
        [
            {
                "doc": "doc-g",
                "versao": "ver-g",
                "texto": texto,
                "ocorrencias": [("legislacao", "legislacao", "Gigante", None)],
            }
        ],
    )
    saida = tmp_path / "gigante.csv"
    gerar_recorte(base, saida)
    settings = Settings()
    client = _memoria(settings)
    embed = _EmbedFalso()
    ingerir(saida, settings=settings, client=client, embed=embed, colecao=COLECAO)
    assert embed.textos
    assert max(len(t) for t in embed.textos) <= LIMITE_CORPO + 400
    emitido = " ".join(embed.textos)
    assert all(w in emitido for w in palavras[::997])
    assert palavras[-1] in emitido


def test_partir_corpo_limita_e_nao_deixa_buraco():
    grande = "x" * 5000
    texto = "\n\n".join(["a" * 900, "b" * 900, grande, "d" * 100])
    intervalos = partir_corpo(texto, 2000, 200)
    assert all(b - a <= 2000 for a, b in intervalos)
    assert intervalos[0][0] == 0
    assert intervalos[-1][1] == len(texto)
    for (a1, b1), (a2, b2) in zip(intervalos, intervalos[1:]):
        assert a2 <= b1
    janelas = [(a, b) for a, b in intervalos if b - a == 2000]
    assert janelas[1][0] - janelas[0][0] == 1800


def test_rasuras_saem_do_texto_emitido_e_original_fica_no_payload(tmp_path):
    texto = (
        "Art. 1º Valor ~~R$ 10~~ R$ 20 vigente.\n\n"
        "> Marcadores da fonte: tachado\n\nTexto revogado inteiro.\n\n"
        "Art. 2º Fica mantido.\n\n"
        "> Marcadores da fonte: omitir\n\nTexto omitido pela fonte."
    )
    base = montar_run(
        tmp_path / "r",
        [
            {
                "doc": "doc-r",
                "versao": "ver-r",
                "texto": texto,
                "ocorrencias": [("legislacao", "legislacao", "Lei R", None)],
            }
        ],
    )
    saida = tmp_path / "r.csv"
    gerar_recorte(base, saida)
    assert _linhas(saida)["doc-r"]["texto"] == texto  # CSV intacto
    settings = Settings()
    client = _memoria(settings)
    embed = _EmbedFalso()
    stats = ingerir(saida, settings=settings, client=client, embed=embed, colecao=COLECAO)
    emitido = " ".join(embed.textos)
    assert "~~" not in emitido
    assert "Texto revogado inteiro" not in emitido
    assert "R$ 20 vigente" in emitido and "Fica mantido" in emitido
    assert "Texto omitido pela fonte" in emitido  # omitir não é removido
    com_original = [p.payload for p in _pontos(client) if "texto_com_rasuras" in p.payload]
    assert com_original
    assert any("~~R$ 10~~" in p["texto_com_rasuras"] for p in com_original)
    assert any("Texto revogado inteiro" in p["texto_com_rasuras"] for p in com_original)
    assert stats["pontos_com_rasura"] == len(com_original)


def test_chunk_totalmente_riscado_nao_sobe(tmp_path):
    texto = "Art. 1º ~~tudo~~\n\n> Marcadores da fonte: tachado\n\nSó riscado.\n\nArt. 2º ~~x~~"
    base = montar_run(
        tmp_path / "t",
        [
            {
                "doc": "doc-t",
                "versao": "ver-t",
                "texto": texto,
                "ocorrencias": [("legislacao", "legislacao", "Lei T", None)],
            }
        ],
    )
    saida = tmp_path / "t.csv"
    gerar_recorte(base, saida)
    settings = Settings()
    client = _memoria(settings)
    embed = _EmbedFalso()
    stats = ingerir(saida, settings=settings, client=client, embed=embed, colecao=COLECAO)
    assert stats["riscados_integralmente"] == 2  # Art. 1º e Art. 2º
    assert embed.chamadas == 0
    assert _pontos(client) == []


def test_falha_no_lote_informa_documento_e_chunk(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    linha = next(iter(ler_csv(saida)))
    primeiro_chunk = next(itens_do_documento(linha, estatisticas_novas()))[2]["chunk_id"]

    def embed_quebrado(textos):
        raise ConnectionError("ollama fora")

    with pytest.raises(RuntimeError, match="doc-a") as exc:
        ingerir(
            saida,
            settings=Settings(),
            client=_memoria(Settings()),
            embed=embed_quebrado,
            colecao=COLECAO,
        )
    assert primeiro_chunk in str(exc.value)


def test_retentativas_recuperam_falha_passageira_do_embed():
    chamadas = []
    esperas = []

    def embed(textos):
        chamadas.append(textos)
        if len(chamadas) < 3:
            raise DependencyUnavailable("Não foi possível consultar Ollama.")
        return [[0.0]]

    resultado = com_retentativas(embed, esperas=(1, 2, 3), dormir=esperas.append)(["a"])
    assert resultado == [[0.0]]
    assert esperas == [1, 2]


def test_retentativas_desistem_e_repassam_o_erro():
    esperas = []

    def embed(textos):
        raise DependencyUnavailable("fora do ar")

    with pytest.raises(DependencyUnavailable):
        com_retentativas(embed, esperas=(1, 2), dormir=esperas.append)(["a"])
    assert esperas == [1, 2]


def test_retomar_pula_documento_completo_e_refaz_o_incompleto(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    settings = Settings()
    client = _memoria(settings)
    ingerir(saida, settings=settings, client=client, embed=_EmbedFalso(), colecao=COLECAO)
    total = client.count(COLECAO, exact=True).count

    def embed_proibido(textos):
        raise AssertionError("documento completo não pode ser embeddado de novo")

    r = ingerir(
        saida, settings=settings, client=client, embed=embed_proibido, colecao=COLECAO, retomar=True
    )
    assert (r["gravados"], r["pulados"]) == (0, 2)

    doc_a = [p.id for p in _pontos(client) if p.payload["document_id"] == "doc-a"]
    client.delete(COLECAO, points_selector=doc_a[:1])
    r = ingerir(
        saida, settings=settings, client=client, embed=_EmbedFalso(), colecao=COLECAO, retomar=True
    )
    assert (r["gravados"], r["pulados"]) == (len(doc_a), 1)
    assert client.count(COLECAO, exact=True).count == total
