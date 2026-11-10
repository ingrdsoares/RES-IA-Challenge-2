"""Ponte do recorte CSV (recorte_csv) para uma coleção Qdrant.

Reusa a configuração, o cliente Ollama e o VectorStore da API (backend/api/app).
Documentos são embeddados sem o prefixo de instrução que a API põe na pergunta
(QUERY_INSTRUCTION em app/models.py): o prefixo é só do lado da consulta.

Antes de embeddar, o texto do chunk recebe duas regras de fonte (só aqui; o CSV não muda):
- remove spans ~~riscado~~ e blocos "> Marcadores da fonte: tachado" (o bloco é o
  parágrafo seguinte, até a próxima linha em branco);
- "omitir" não é removido. Trechos sem nada depois da remoção não sobem.
O texto original de cada ponto com rasura fica em `texto_com_rasuras`.

Uso:
  python -m src.rag.csv_para_qdrant --csv <arquivo.csv> --dry-run
  python -m src.rag.csv_para_qdrant --csv <arquivo.csv> --colecao <nome> [--limite N]
"""

import argparse
import csv
import gzip
import itertools
import re
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

BACKEND_API = Path(__file__).resolve().parents[2] / "backend" / "api"
if str(BACKEND_API) not in sys.path:
    sys.path.insert(0, str(BACKEND_API))

from app.config import Settings  # noqa: E402
from app.errors import DependencyUnavailable, dependency_errors  # noqa: E402
from app.models import LocalModels  # noqa: E402
from app.vector_store import VectorStore  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client import models as qm  # noqa: E402

from src.rag.chunker import LegalHierarchicalChunker  # noqa: E402

TAMANHO_LOTE = 64
LIMITE_CORPO = 2000
SOBREPOSICAO = 200
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "socio-digital/recorte-rag-v1")
CHUNKER = LegalHierarchicalChunker()

_RASURA = re.compile(r"~~.*?~~", re.DOTALL)
_MARCA = r"(?![ \t]*(?:## |> Marcadores))"
_TACHADO = re.compile(
    r"^> Marcadores da fonte: tachado[ \t]*\n(?:[ \t]*\n)*"
    + _MARCA
    + r"[ \t]*\S[^\n]*(?:\n"
    + _MARCA
    + r"[ \t]*\S[^\n]*)*",
    re.MULTILINE,
)

Embed = Callable[[list[str]], list[list[float]]]


def estatisticas_novas() -> dict[str, int]:
    return {
        "documentos": 0,
        "chunks_base": 0,
        "riscados_integralmente": 0,
        "partes_vazias": 0,
        "pontos": 0,
        "pontos_com_rasura": 0,
        "max_texto": 0,
        "bytes_texto": 0,
    }


def ler_csv(caminho: Path) -> Iterator[dict]:
    csv.field_size_limit(2**31 - 1)
    if str(caminho).endswith(".gz"):
        f = gzip.open(caminho, "rt", encoding="utf-8", newline="")
    else:
        f = open(caminho, encoding="utf-8", newline="")
    with f:
        yield from csv.DictReader(f)


def ponto_id(versao_id: str, indice: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{versao_id}:{indice}"))


def remover_rasuras(bruto: str) -> tuple[str, list[int]]:
    """Texto sem rasuras e, para cada caractere dele, a posição no texto bruto."""
    spans = sorted(
        [m.span() for m in _RASURA.finditer(bruto)] + [m.span() for m in _TACHADO.finditer(bruto)]
    )
    fundidos: list[list[int]] = []
    for a, b in spans:
        if fundidos and a <= fundidos[-1][1]:
            fundidos[-1][1] = max(fundidos[-1][1], b)
        else:
            fundidos.append([a, b])
    partes: list[str] = []
    mapa: list[int] = []
    pos = 0
    for a, b in fundidos:
        partes.append(bruto[pos:a])
        mapa.extend(range(pos, a))
        pos = b
    partes.append(bruto[pos:])
    mapa.extend(range(pos, len(bruto)))
    return "".join(partes), mapa


def partir_corpo(texto: str, limite: int, sobreposicao: int) -> list[tuple[int, int]]:
    """Intervalos [a, b) de até `limite` caracteres, por parágrafo; parágrafo maior vira janelas."""
    n = len(texto)
    if n <= limite:
        return [(0, n)]
    paragrafos: list[tuple[int, int]] = []
    pos = 0
    for m in re.finditer(r"\n[ \t]*\n", texto):
        paragrafos.append((pos, m.end()))
        pos = m.end()
    if pos < n:
        paragrafos.append((pos, n))
    intervalos: list[tuple[int, int]] = []
    atual: tuple[int, int] | None = None
    for a, b in paragrafos:
        if b - a > limite:
            if atual is not None:
                intervalos.append(atual)
                atual = None
            i = a
            while True:
                fim = min(i + limite, b)
                intervalos.append((i, fim))
                if fim == b:
                    break
                i = fim - sobreposicao
        elif atual is None:
            atual = (a, b)
        elif b - atual[0] <= limite:
            atual = (atual[0], b)
        else:
            intervalos.append(atual)
            atual = (a, b)
    if atual is not None:
        intervalos.append(atual)
    return intervalos


def itens_do_documento(
    linha: dict, estatisticas: dict[str, int]
) -> Iterator[tuple[str, str, dict]]:
    """(id do ponto, texto a embeddar, payload) de cada ponto do documento."""
    indice = 0
    for chunk in CHUNKER.chunk_document(linha["texto"], linha["titulo"]):
        estatisticas["chunks_base"] += 1
        bruto = chunk.raw_text
        cabecalho = (
            chunk.content[: len(chunk.content) - len(bruto)]
            if chunk.content.endswith(bruto)
            else ""
        )
        limpo, mapa = remover_rasuras(bruto)
        if not limpo.strip():
            estatisticas["riscados_integralmente"] += 1
            continue
        trechos = []
        for a, b in partir_corpo(limpo, LIMITE_CORPO, SOBREPOSICAO):
            trecho = limpo[a:b]
            if not trecho.strip():
                estatisticas["partes_vazias"] += 1
                continue
            ini = 0 if a == 0 else mapa[a]
            fim = len(bruto) if b >= len(limpo) else mapa[b]
            trechos.append((trecho, bruto[ini:fim]))
        for k, (trecho, original) in enumerate(trechos, 1):
            texto = cabecalho + trecho
            dados = {
                "text": texto,
                "source": linha["source_url"],
                "title": linha["titulo"] or None,
                "document_id": linha["documento_id"],
                "chunk_id": chunk.chunk_id if len(trechos) == 1 else f"{chunk.chunk_id}#{k}",
            }
            if original != trecho:
                dados["texto_com_rasuras"] = cabecalho + original
                estatisticas["pontos_com_rasura"] += 1
            estatisticas["pontos"] += 1
            estatisticas["max_texto"] = max(estatisticas["max_texto"], len(texto))
            estatisticas["bytes_texto"] += len(texto.encode("utf-8"))
            yield ponto_id(linha["versao_id"], indice), texto, dados
            indice += 1


def _apagar_documento(client: QdrantClient, colecao: str, documento_id: str) -> None:
    filtro = qm.Filter(
        must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=documento_id))]
    )
    try:
        client.delete(collection_name=colecao, points_selector=qm.FilterSelector(filter=filtro))
    except Exception as exc:
        raise RuntimeError(
            f"falha ao apagar pontos antigos do documento {documento_id}: {exc}"
        ) from exc


def _gravar(client: QdrantClient, colecao: str, embed: Embed, lote: list) -> None:
    primeiro = lote[0][2]
    ultimo = lote[-1][2]
    try:
        vetores = embed([texto for _, texto, _ in lote])
        if len(vetores) != len(lote):
            raise DependencyUnavailable("Quantidade de embeddings diferente da de chunks.")
        client.upsert(
            collection_name=colecao,
            points=[
                qm.PointStruct(id=pid, vector=vetor, payload=dados)
                for (pid, _, dados), vetor in zip(lote, vetores, strict=True)
            ],
        )
    except Exception as exc:
        raise RuntimeError(
            f"falha ao gravar lote: documento {primeiro['document_id']}, "
            f"chunk {primeiro['chunk_id']} até documento {ultimo['document_id']}, "
            f"chunk {ultimo['chunk_id']}: {exc}"
        ) from exc


def ingerir(
    caminho_csv: Path,
    *,
    settings: Settings,
    client: QdrantClient,
    embed: Embed,
    colecao: str,
    limite: int | None = None,
) -> dict[str, int]:
    VectorStore(
        settings.model_copy(update={"collection_name": colecao}), client
    ).ensure_collection()
    estatisticas = estatisticas_novas()
    gravados = 0
    lote: list = []
    apagados: set[str] = set()
    for linha in itertools.islice(ler_csv(caminho_csv), limite):
        documento = linha["documento_id"]
        if documento not in apagados:
            _apagar_documento(client, colecao, documento)
            apagados.add(documento)
        estatisticas["documentos"] += 1
        for item in itens_do_documento(linha, estatisticas):
            lote.append(item)
            if len(lote) == TAMANHO_LOTE:
                _gravar(client, colecao, embed, lote)
                gravados += len(lote)
                lote = []
    if lote:
        _gravar(client, colecao, embed, lote)
        gravados += len(lote)
    return estatisticas | {"gravados": gravados}


def resumo_dry_run(caminho_csv: Path, *, settings: Settings, limite: int | None = None) -> dict:
    estatisticas = estatisticas_novas()
    for linha in itertools.islice(ler_csv(caminho_csv), limite):
        estatisticas["documentos"] += 1
        for _ in itens_do_documento(linha, estatisticas):
            pass
    estatisticas["bytes_vetores_estimados"] = (
        estatisticas["pontos"] * settings.embedding_dimensions * 4
    )
    return estatisticas


def embedder_ollama(settings: Settings) -> Embed:
    models = LocalModels(settings)

    def embed(textos: list[str]) -> list[list[float]]:
        with dependency_errors("Ollama"):
            vetores = models.client.embed(
                model=settings.embedding_model, input=textos, truncate=False
            ).embeddings
        if len(vetores) != len(textos) or any(
            len(v) != settings.embedding_dimensions for v in vetores
        ):
            raise DependencyUnavailable("Embedding inválido retornado pelo Ollama.")
        return [list(v) for v in vetores]

    return embed


def main(
    argv: list[str] | None = None,
    *,
    embed: Embed | None = None,
    client: QdrantClient | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Sobe o recorte CSV para uma coleção Qdrant.")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--colecao", default=None, help="obrigatório na gravação (sem padrão)")
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings()

    if args.dry_run:
        r = resumo_dry_run(args.csv, settings=settings, limite=args.limite)
        for chave in (
            "documentos",
            "chunks_base",
            "pontos",
            "riscados_integralmente",
            "partes_vazias",
            "pontos_com_rasura",
            "max_texto",
            "bytes_texto",
            "bytes_vetores_estimados",
        ):
            print(f"{chave}: {r[chave]}")
        return 0

    if not args.colecao:
        parser.error("--colecao é obrigatório para gravar (não há padrão)")
    if client is None:
        client = QdrantClient(url=str(settings.qdrant_url), timeout=settings.qdrant_timeout)
    if embed is None:
        embed = embedder_ollama(settings)
    r = ingerir(
        args.csv,
        settings=settings,
        client=client,
        embed=embed,
        colecao=args.colecao,
        limite=args.limite,
    )
    for chave in (
        "documentos",
        "pontos",
        "gravados",
        "riscados_integralmente",
        "partes_vazias",
        "pontos_com_rasura",
    ):
        print(f"{chave}: {r[chave]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
