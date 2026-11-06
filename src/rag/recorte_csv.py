"""Recorte RAG v1: exporta o índice núcleo do refino (versão preferida por documento) para CSV.

O CSV é entrada de pipeline (lida por csv_para_qdrant), não planilha: o texto sai sem
alteração e sem neutralização de fórmulas.

Uso: python -m src.rag.recorte_csv --run <dir do refino> --saida <arquivo.csv>
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

NATUREZAS_PERMITIDAS = frozenset(
    {
        "legislacao",
        "ato_normativo_administrativo",
        "interpretacao_administrativa",
        "consulta_tributaria",
        "jurisprudencia_tarf",
        "anexo_convertido",
        "quadro_sumulas_com_referencias_precedentes",
        "orientacao_oficial",
        "consulta_acordao_administrativo",
        "diario_com_consulta_tributaria",
        "diario_com_jurisprudencia_tributaria",
        "informativo_jurisprudencial",
        "perguntas_respostas",
        "orientacao_mei",
        "manual",
        "documentacao_classificacao_oficial",
    }
)
# Natureza genérica do refino: entra só quando título ou chave_origem identifica ato legal.
NATUREZAS_CONDICIONAIS = frozenset({"nao_informada", "pagina_oficial"})
_ATO_LEGAL = re.compile(
    r"\b(?:lei|lc|decreto|dl|portaria|in|ajuste|convenio|emenda)\b|df-(?:lei|decreto)-"
)
# O refino grava "nao_verificada" em toda ocorrência: não é informação da fonte.
VIGENCIAS_SEM_INFORMACAO = frozenset({"", "nao_verificada"})
TETO_BYTES = 1024**3
COLUNAS = (
    "documento_id",
    "versao_id",
    "titulo",
    "natureza",
    "frente",
    "chave_origem",
    "source_url",
    "coletado_em",
    "vigencia_fonte",
    "texto",
)


class CsvAcimaDoTeto(Exception):
    """O CSV passaria do teto de bytes; a saída parcial é removida, nada é truncado."""


def _jsonl(caminho: Path):
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                yield json.loads(linha)


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


_HOST = re.compile(r"https?://[^/\s]+")


def _ato_legal(ocorrencia: dict) -> bool:
    # O host sai da busca: "in.gov.br" não pode fazer uma página do portal passar por IN.
    texto = _HOST.sub(" ", f"{ocorrencia['titulo']} {ocorrencia['chave_origem']}")
    return bool(_ATO_LEGAL.search(_sem_acento(texto)))


def _permitida(ocorrencia: dict) -> bool:
    natureza = ocorrencia["natureza"]
    if natureza in NATUREZAS_PERMITIDAS:
        return True
    return natureza in NATUREZAS_CONDICIONAIS and _ato_legal(ocorrencia)


def _motivo_exclusao(ocorrencias: list[dict]) -> str | None:
    """Documento entra só se todas as ocorrências da versão forem permitidas."""
    if any(o["frente"].startswith("cnpj") for o in ocorrencias):
        return "frente_cnpj"
    for o in ocorrencias:
        if not _permitida(o):
            return o["natureza"]
    return None


def gerar_recorte(run: Path, saida: Path, teto_bytes: int = TETO_BYTES) -> dict:
    run = Path(run)
    saida = Path(saida)
    versoes = {v["id"]: v for v in _jsonl(run / "versoes.jsonl")}
    ocorrencias = {o["id"]: o for o in _jsonl(run / "ocorrencias.jsonl")}

    saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = saida.with_name(saida.name + ".tmp")
    sha = hashlib.sha256()
    total = 0
    linhas = 0
    por_natureza: Counter = Counter()
    bytes_por_natureza: Counter = Counter()
    excluidos: dict[str, dict[str, int]] = {}
    condicionais_excluidos: list[dict] = []

    try:
        with open(tmp, "wb") as f:

            def escrever(registro):
                nonlocal total
                buffer = io.StringIO()
                csv.writer(buffer, lineterminator="\n").writerow(registro)
                dados = buffer.getvalue().encode("utf-8")
                total += len(dados)
                if total > teto_bytes:
                    raise CsvAcimaDoTeto(f"CSV passaria de {teto_bytes} bytes; nada foi gravado.")
                sha.update(dados)
                f.write(dados)

            escrever(COLUNAS)
            for nucleo in _jsonl(run / "indice_nucleo.jsonl"):
                versao = versoes[nucleo["representacao_preferida"]]
                ocs = [ocorrencias[i] for i in versao["ocorrencias"]]
                conteudo_id = versao["conteudo_id"]
                caminho_texto = run / "conteudos" / f"{conteudo_id}.md" if conteudo_id else None
                motivo = "sem_texto" if caminho_texto is None else _motivo_exclusao(ocs)
                if motivo:
                    tamanho = caminho_texto.stat().st_size if caminho_texto else 0
                    registro = excluidos.setdefault(motivo, {"documentos": 0, "bytes_texto": 0})
                    registro["documentos"] += 1
                    registro["bytes_texto"] += tamanho
                    if motivo in NATUREZAS_CONDICIONAIS:
                        condicionais_excluidos.append(
                            {
                                "natureza": motivo,
                                "titulo": ocs[0]["titulo"],
                                "chave_origem": ocs[0]["chave_origem"],
                            }
                        )
                    continue

                rep = ocs[0]
                texto = caminho_texto.read_bytes().decode("utf-8")
                vigencia = "" if rep["vigencia"] in VIGENCIAS_SEM_INFORMACAO else rep["vigencia"]
                escrever(
                    [
                        nucleo["documento_id"],
                        versao["id"],
                        rep["titulo"],
                        rep["natureza"],
                        rep["frente"],
                        rep["chave_origem"],
                        rep["source_url"],
                        rep["coletado_em"],
                        vigencia,
                        texto,
                    ]
                )
                linhas += 1
                por_natureza[rep["natureza"]] += 1
                bytes_por_natureza[rep["natureza"]] += len(texto.encode("utf-8"))
        os.replace(tmp, saida)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    manifesto = {
        "run": str(run),
        "saida": str(saida),
        "colunas": list(COLUNAS),
        "naturezas_permitidas": sorted(NATUREZAS_PERMITIDAS),
        "linhas": linhas,
        "bytes": total,
        "sha256": sha.hexdigest(),
        "teto_bytes": teto_bytes,
        "contagens_por_natureza": dict(por_natureza),
        "bytes_texto_por_natureza": dict(bytes_por_natureza),
        "excluidos": excluidos,
        "condicionais_excluidos": condicionais_excluidos,
    }
    saida.with_name(saida.name + ".manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifesto


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exporta o recorte RAG v1 do refino para CSV.")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--saida", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifesto = gerar_recorte(args.run, args.saida)
    except CsvAcimaDoTeto as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"linhas: {manifesto['linhas']} bytes: {manifesto['bytes']}")
    print(f"sha256: {manifesto['sha256']}")
    for natureza, n in sorted(manifesto["contagens_por_natureza"].items()):
        print(f"incluido {natureza}: {n}")
    for motivo, dados in sorted(manifesto["excluidos"].items()):
        print(f"excluido {motivo}: {dados['documentos']} docs, {dados['bytes_texto']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
