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
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

BACKEND_API = Path(__file__).resolve().parents[2] / "backend" / "api"
if str(BACKEND_API) not in sys.path:
    sys.path.insert(0, str(BACKEND_API))

from app.config import Settings  # noqa: E402
from app.errors import DependencyUnavailable, dependency_errors  # noqa: E402
from app.models import LocalModels  # noqa: E402
from app.normas import chave_artigo, chaves_normas  # noqa: E402
from app.sparse import vetor_documento  # noqa: E402
from app.vector_store import DENSE, SPARSE, VectorStore  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client import models as qm  # noqa: E402

from backend.cleaning.limpeza_markdown import limpar_markdown  # noqa: E402
from src.rag.chunker import LegalHierarchicalChunker  # noqa: E402

TAMANHO_LOTE = 64
LIMITE_CORPO = 2000
SOBREPOSICAO = 200
# Até 120 s: é quanto o Windows segura um socket em TIME_WAIT.
ESPERAS_RETENTATIVA = (30, 60, 120, 120, 120)
# O timeout da API (5 s) é para consulta; numa carga longa o upsert passa disso.
TIMEOUT_QDRANT_CARGA = 120
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "socio-digital/recorte-rag-v1")
CHUNKER = LegalHierarchicalChunker()
# Ligada por --limpar; desligada mantém a carga igual à da knowledge_base_v2.
LIMPAR = False


def configurar(limite_corpo: int, limpar: bool) -> None:
    """Tamanho do chunk e limpeza da carga; ids de ponto mudam, então use outra coleção."""
    global LIMITE_CORPO, SOBREPOSICAO, CHUNKER, LIMPAR
    LIMITE_CORPO = limite_corpo
    SOBREPOSICAO = limite_corpo // 10
    CHUNKER = LegalHierarchicalChunker(max_chunk_chars=limite_corpo, overlap_chars=SOBREPOSICAO)
    LIMPAR = limpar


# Páginas de login do gov.br coletadas no lugar das súmulas do CARF; não têm conteúdo.
TITULO_PAGINA_LOGIN = "Conteúdo Restrito"

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

_SEGMENTO = re.compile(r"^## Segmento (\d+) — versão (\d+)[ \t]*$", re.MULTILINE)

Embed = Callable[[list[str]], list[list[float]]]


def estatisticas_novas() -> dict[str, int]:
    return {
        "documentos": 0,
        "pulados": 0,
        "paginas_login": 0,
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


def limpar_segmentos(texto: str) -> str:
    """Tira os cabeçalhos "## Segmento N — versão M" e as repetições idênticas de segmento.

    Versões diferentes do mesmo segmento ficam marcadas: qual delas vale não é inferido aqui.
    """
    partes = _SEGMENTO.split(texto)
    if len(partes) == 1:
        return texto
    versoes: dict[str, set[str]] = {}
    for segmento, versao in zip(partes[1::3], partes[2::3], strict=True):
        versoes.setdefault(segmento, set()).add(versao)
    vistos: set[tuple[str, str, str]] = set()
    saida = [partes[0]]
    for segmento, versao, corpo in zip(partes[1::3], partes[2::3], partes[3::3], strict=True):
        chave = (segmento, versao, corpo.strip())
        if chave in vistos:
            continue
        vistos.add(chave)
        if len(versoes[segmento]) > 1:
            saida.append(f"[Versão {versao} deste trecho]\n")
        saida.append(corpo)
    return "".join(saida)


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
    texto_doc = limpar_segmentos(linha["texto"])
    if LIMPAR:
        texto_doc = limpar_markdown(texto_doc)
    for chunk in CHUNKER.chunk_document(texto_doc, linha["titulo"]):
        estatisticas["chunks_base"] += 1
        bruto = chunk.raw_text
        cabecalho = (
            chunk.content[: len(chunk.content) - len(bruto)]
            if chunk.content.endswith(bruto)
            else ""
        )
        limpo, mapa = remover_rasuras(bruto)
        # Sobrar só o número do artigo também é chunk sem conteúdo.
        if limpo.strip() in ("", chunk.artigo):
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
                "norma": chaves_normas(linha["titulo"]),
                "artigo": chave_artigo(chunk.artigo),
                "frente": linha.get("frente") or None,
                "natureza": linha.get("natureza") or None,
                "ordem": indice,
            }
            if original != trecho:
                dados["texto_com_rasuras"] = cabecalho + original
                estatisticas["pontos_com_rasura"] += 1
            estatisticas["pontos"] += 1
            estatisticas["max_texto"] = max(estatisticas["max_texto"], len(texto))
            estatisticas["bytes_texto"] += len(texto.encode("utf-8"))
            yield ponto_id(linha["versao_id"], indice), texto, dados
            indice += 1


def _filtro_documento(documento_id: str) -> qm.Filter:
    return qm.Filter(
        must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=documento_id))]
    )


def _pontos_do_documento(client: QdrantClient, colecao: str, documento_id: str) -> int:
    filtro = _filtro_documento(documento_id)
    return client.count(colecao, count_filter=filtro, exact=True).count


def _apagar_documento(client: QdrantClient, colecao: str, documento_id: str) -> None:
    filtro = _filtro_documento(documento_id)
    try:
        client.delete(collection_name=colecao, points_selector=qm.FilterSelector(filter=filtro))
    except Exception as exc:
        raise RuntimeError(
            f"falha ao apagar pontos antigos do documento {documento_id}: {exc}"
        ) from exc


def _vetores(texto: str, denso: list[float]) -> dict:
    indices, valores = vetor_documento(texto)
    return {DENSE: denso, SPARSE: qm.SparseVector(indices=indices, values=valores)}


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
                qm.PointStruct(id=pid, vector=_vetores(texto, vetor), payload=dados)
                for (pid, texto, dados), vetor in zip(lote, vetores, strict=True)
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
    retomar: bool = False,
) -> dict[str, int]:
    VectorStore(
        settings.model_copy(update={"collection_name": colecao}), client
    ).ensure_collection()
    # Sem índice, cada exclusão por documento varre a coleção inteira.
    for campo in ("document_id", "norma", "artigo", "frente"):
        client.create_payload_index(colecao, campo, qm.PayloadSchemaType.KEYWORD, wait=True)
    client.create_payload_index(colecao, "ordem", qm.PayloadSchemaType.INTEGER, wait=True)
    estatisticas = estatisticas_novas()
    gravados = 0
    lote: list = []
    apagados: set[str] = set()
    for linha in itertools.islice(ler_csv(caminho_csv), limite):
        documento = linha["documento_id"]
        estatisticas["documentos"] += 1
        if linha["titulo"].strip() == TITULO_PAGINA_LOGIN:
            _apagar_documento(client, colecao, documento)
            estatisticas["paginas_login"] += 1
            continue
        itens = list(itens_do_documento(linha, estatisticas))
        if retomar and documento not in apagados:
            if _pontos_do_documento(client, colecao, documento) == len(itens):
                estatisticas["pulados"] += 1
                continue
        if documento not in apagados:
            _apagar_documento(client, colecao, documento)
            apagados.add(documento)
        for item in itens:
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


def com_retentativas(
    embed: Embed,
    esperas: tuple[int, ...] = ESPERAS_RETENTATIVA,
    dormir: Callable[[float], None] = time.sleep,
) -> Embed:
    """Repete o lote após falha passageira do Ollama; a carga não retoma se o processo cair."""

    def tentar(textos: list[str]) -> list[list[float]]:
        for espera in esperas:
            try:
                return embed(textos)
            except DependencyUnavailable as exc:
                print(f"embed falhou ({exc}); nova tentativa em {espera} s", file=sys.stderr)
                dormir(espera)
        return embed(textos)

    return tentar


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
    parser.add_argument(
        "--retomar",
        action="store_true",
        help="pula documento com todos os pontos já gravados; só para o mesmo CSV e chunker",
    )
    parser.add_argument(
        "--limite-corpo",
        type=int,
        default=2000,
        help="caracteres por chunk (sobreposição de 10%%); padrão 2000",
    )
    parser.add_argument(
        "--limpar", action="store_true", help="aplica backend/cleaning/limpeza_markdown"
    )
    args = parser.parse_args(argv)
    configurar(args.limite_corpo, args.limpar)
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
        client = QdrantClient(url=str(settings.qdrant_url), timeout=TIMEOUT_QDRANT_CARGA)
    if embed is None:
        embed = com_retentativas(embedder_ollama(settings))
    r = ingerir(
        args.csv,
        settings=settings,
        client=client,
        embed=embed,
        colecao=args.colecao,
        limite=args.limite,
        retomar=args.retomar,
    )
    for chave in (
        "documentos",
        "pulados",
        "paginas_login",
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
