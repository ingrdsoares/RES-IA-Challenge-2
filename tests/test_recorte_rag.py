import csv
import hashlib
import json
from pathlib import Path

import pytest
from app.config import Settings
from app.schemas import Source
from qdrant_client import QdrantClient

from src.rag.csv_para_qdrant import ingerir, ler_csv
from src.rag.csv_para_qdrant import main as main_ponte
from src.rag.recorte_csv import (
    COLUNAS,
    NATUREZAS_PERMITIDAS,
    CsvAcimaDoTeto,
    gerar_recorte,
)

TEXTO_A = 'Art. 1º Texto com "aspas", vírgula;\nlinha ~~rasura~~ e =SOMA(A1)\n\nArt. 2º Segundo.'
TEXTO_D = "Art. 1º Orientação oficial curta."


def _escrever_jsonl(caminho: Path, registros: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


@pytest.fixture
def run(tmp_path):
    """Run fictício: A (legislacao, + versão não preferida), B (nao_informada), C (cnpj), D (orientacao)."""
    base = tmp_path / "run"

    def ocorrencia(oid, versao, doc, conteudo, natureza, frente, titulo):
        return {
            "id": oid,
            "versao_id": versao,
            "documento_id": doc,
            "conteudo_id": conteudo,
            "natureza": natureza,
            "frente": frente,
            "classificacao": "nucleo",
            "source_url": f"https://fonte.test/{oid}",
            "titulo": titulo,
            "coletado_em": "2026-11-04T10:00:00+00:00",
            "chave_origem": f"url:{oid}",
            "vigencia": "nao_verificada",
            "bytes_texto": 10,
        }

    ocorrencias = [
        ocorrencia("oc-a1", "ver-a1", "doc-a", "ca1", "legislacao", "legislacao", "Lei A"),
        ocorrencia("oc-a2", "ver-a2", "doc-a", "ca2", "legislacao", "legislacao", "Lei A antiga"),
        ocorrencia("oc-b", "ver-b", "doc-b", "cb", "nao_informada", "legislacao", "Ato B"),
        ocorrencia("oc-c", "ver-c", "doc-c", "cc", "legislacao", "cnpj-df", "Dado C"),
        ocorrencia("oc-d", "ver-d", "doc-d", "cd", "orientacao_oficial", "manuais", "Guia D"),
    ]
    versoes = [
        {"id": v, "documento_id": d, "conteudo_id": c, "ocorrencias": [o]}
        for v, d, c, o in [
            ("ver-a1", "doc-a", "ca1", "oc-a1"),
            ("ver-a2", "doc-a", "ca2", "oc-a2"),
            ("ver-b", "doc-b", "cb", "oc-b"),
            ("ver-c", "doc-c", "cc", "oc-c"),
            ("ver-d", "doc-d", "cd", "oc-d"),
        ]
    ]
    documentos = [
        {
            "id": d,
            "naturezas": [n],
            "chave_origem": f"url:{d}",
            "titulos": [t],
            "representacao_preferida": v,
            "versoes": [v],
            "ocorrencias": [o],
            "categorias": ["nucleo"],
            "criterio_representacao": "x",
        }
        for d, n, t, v, o in [
            ("doc-a", "legislacao", "Lei A", "ver-a1", "oc-a1"),
            ("doc-b", "nao_informada", "Ato B", "ver-b", "oc-b"),
            ("doc-c", "legislacao", "Dado C", "ver-c", "oc-c"),
            ("doc-d", "orientacao_oficial", "Guia D", "ver-d", "oc-d"),
        ]
    ]
    nucleo = [
        {
            "documento_id": d["id"],
            "representacao_preferida": d["representacao_preferida"],
            "revisao_semantica": "pendente",
            "titulos": d["titulos"],
            "versoes": d["versoes"],
        }
        for d in documentos
    ]
    _escrever_jsonl(base / "ocorrencias.jsonl", ocorrencias)
    _escrever_jsonl(base / "versoes.jsonl", versoes)
    _escrever_jsonl(base / "documentos.jsonl", documentos)
    _escrever_jsonl(base / "indice_nucleo.jsonl", nucleo)
    for conteudo, texto in [
        ("ca1", TEXTO_A),
        ("ca2", "Art. 1º versão antiga."),
        ("cb", "Art. 1º B."),
        ("cc", "Art. 1º C."),
        ("cd", TEXTO_D),
    ]:
        (base / "conteudos").mkdir(exist_ok=True)
        (base / "conteudos" / f"{conteudo}.md").write_bytes(texto.encode("utf-8"))
    return base


def test_csv_ida_e_volta_preserva_texto_e_colunas(run, tmp_path):
    saida = tmp_path / "out" / "recorte.csv"
    gerar_recorte(run, saida)
    with open(saida, encoding="utf-8", newline="") as f:
        leitor = csv.DictReader(f)
        assert leitor.fieldnames == list(COLUNAS)
        linhas = {r["documento_id"]: r for r in leitor}
    assert set(linhas) == {"doc-a", "doc-d"}
    assert linhas["doc-a"]["texto"] == TEXTO_A
    assert linhas["doc-a"]["versao_id"] == "ver-a1"
    assert linhas["doc-a"]["source_url"] == "https://fonte.test/oc-a1"
    assert linhas["doc-a"]["vigencia_fonte"] == ""
    assert linhas["doc-a"]["texto"].startswith("Art. 1º")


def test_allowlist_exclui_natureza_fora_e_cnpj(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    manifesto = gerar_recorte(run, saida)
    assert "nao_informada" not in NATUREZAS_PERMITIDAS
    assert manifesto["excluidos"]["nao_informada"]["documentos"] == 1
    assert manifesto["excluidos"]["nao_informada"]["bytes_texto"] == len("Art. 1º B.".encode())
    assert manifesto["excluidos"]["frente_cnpj"]["documentos"] == 1
    assert manifesto["contagens_por_natureza"] == {"legislacao": 1, "orientacao_oficial": 1}


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
    """Vetores determinísticos de dimensão 1024, sem modelo."""

    def __init__(self):
        self.chamadas = 0

    def __call__(self, textos):
        self.chamadas += 1
        return [[1.0 if i == j % 1024 else 0.0 for j in range(1024)] for i, _ in enumerate(textos)]


def test_ponte_dry_run_nao_chama_modelo_nem_qdrant(run, tmp_path, capsys):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    embed = _EmbedFalso()
    main_ponte(["--csv", str(saida), "--dry-run"], embed=embed, client=None)
    assert embed.chamadas == 0
    assert "documentos: 2" in capsys.readouterr().out


def test_upsert_reexecucao_nao_duplica_e_payload_valida_em_source(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    settings = Settings()
    client = QdrantClient(":memory:")
    from app.vector_store import VectorStore

    VectorStore(settings, client).ensure_collection()
    embed = _EmbedFalso()
    ingerir(saida, settings=settings, client=client, embed=embed)
    total = client.count(settings.collection_name, exact=True).count
    assert total >= 2
    ingerir(saida, settings=settings, client=client, embed=embed)
    assert client.count(settings.collection_name, exact=True).count == total

    pontos, _ = client.scroll(settings.collection_name, limit=100, with_payload=True)
    for ponto in pontos:
        fonte = Source.model_validate(ponto.payload | {"id": ponto.id, "score": 0.0})
        assert fonte.source.startswith("https://fonte.test/")
        assert fonte.effective_date is None
    assert {p.payload["document_id"] for p in pontos} == {"doc-a", "doc-d"}


def test_limite_processa_so_as_primeiras_linhas(run, tmp_path):
    saida = tmp_path / "recorte.csv"
    gerar_recorte(run, saida)
    settings = Settings()
    client = QdrantClient(":memory:")
    from app.vector_store import VectorStore

    VectorStore(settings, client).ensure_collection()
    ingerir(saida, settings=settings, client=client, embed=_EmbedFalso(), limite=1)
    pontos, _ = client.scroll(settings.collection_name, limit=100, with_payload=True)
    assert {p.payload["document_id"] for p in pontos} == {"doc-a"}


def test_ler_csv_aceita_campo_grande(tmp_path):
    caminho = tmp_path / "grande.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(COLUNAS)
        escritor.writerow(["d", "v", "t", "n", "f", "c", "u", "e", "", "x" * 300_000])
    linhas = list(ler_csv(caminho))
    assert len(linhas[0]["texto"]) == 300_000
