"""Recorte RAG v1: exporta o índice núcleo do refino (versão preferida por documento) para CSV.

O CSV é entrada de pipeline (lida por csv_para_qdrant), não planilha: o texto sai sem
alteração e sem neutralização de fórmulas.

Com --publico, o recorte vai para o repositório público: regras aplicadas a documentos
inteiros (nunca texto redigido), CSV comprimido em gzip nível 9 e manifesto que lista cada
documento excluído com título, natureza e regra, sem o valor que casou.

Uso: python -m src.rag.recorte_csv --run <dir do refino> --saida <arquivo.csv> [--publico]
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import shutil
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
# Público: sem as naturezas que nomeiam partes e advogados (jurisprudência, acórdãos, diários).
NATUREZAS_PUBLICO = frozenset(
    {
        "legislacao",
        "ato_normativo_administrativo",
        "anexo_convertido",
        "quadro_sumulas_com_referencias_precedentes",
        "documentacao_classificacao_oficial",
        "orientacao_oficial",
        "orientacao_mei",
        "perguntas_respostas",
        "manual",
        "interpretacao_administrativa",
        "consulta_tributaria",
    }
)
NATUREZAS_EXCLUIDAS_PUBLICO = frozenset(
    {"jurisprudencia_tarf", "consulta_acordao_administrativo", "informativo_jurisprudencial"}
)
# Natureza genérica do refino: entra só quando título ou chave_origem identifica ato legal.
NATUREZAS_CONDICIONAIS = frozenset({"nao_informada", "pagina_oficial"})
# Razão social mista (Ltda, S/A...) só em consultas: legislação não passa por essa regra.
NATUREZAS_MISTO = frozenset({"consulta_tributaria", "interpretacao_administrativa"})
REVISAO_MANUAL_PATH = Path(__file__).with_name("revisao_manual.json")
_ATO_LEGAL = re.compile(
    r"\b(?:lei|lc|decreto|dl|portaria|in|ajuste|convenio|emenda)\b|df-(?:lei|decreto)-"
)
# O refino grava "nao_verificada" em toda ocorrência: não é informação da fonte.
VIGENCIAS_SEM_INFORMACAO = frozenset({"", "nao_verificada"})
TETO_BYTES = 1024**3
TETO_GZ_BYTES = 95 * 10**6
REGRAS_CONTEUDO = {
    "cpf": "CPF real (não máscara nem placeholder) no título ou no texto",
    "cnpj": "CNPJ real (não máscara nem placeholder) no título ou no texto",
    "email": "e-mail fora de .gov.br, .leg.br, .jus.br e .mp.br",
    "oab": "OAB seguida de UF ou número",
    "parte": "linha de parte (interessado, consulente, advogado etc.) preenchida",
    "razao_social": "nome em caixa alta seguido de LTDA, EIRELI, S.A. ou S/A",
    "cf_df": "linha de inscrição CF/DF com número",
    "razao_social_misto": "nome com iniciais maiúsculas seguido de Ltda, S/A, S.A. ou EIRELI (só consultas)",
    "dump_dou": "dump de Diário Oficial (lista de candidatos)",
    "revisao_manual": "documento listado para revisão manual (empresa nomeada sem sufixo)",
}
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

_MASCARA = r"[\dXx*#•]"
_CPF = re.compile(
    rf"(?<![\d.])({_MASCARA}{{3}}\.{_MASCARA}{{3}}\.{_MASCARA}{{3}}-{_MASCARA}{{2}})(?!\d)"
)
_CPF_NU = re.compile(r"CPF\D{0,15}?(\d{11})(?!\d)", re.IGNORECASE)
_CNPJ = re.compile(
    rf"(?<![\d.])({_MASCARA}{{2}}\.{_MASCARA}{{3}}\.{_MASCARA}{{3}}/{_MASCARA}{{4}}-{_MASCARA}{{2}})(?!\d)"
)
# Sem máscara só vale com filial "000N" (CNPJ); "/AAAA-NN" é processo ou ato, não CNPJ.
_CNPJ_NU = re.compile(r"(?<![\d.])(\d{2}\.?\d{3}\.?\d{3}/000\d-?\d{2})(?!\d)")
_MISTO = re.compile(
    r"(?:\b[A-ZÀ-Ú][\wÀ-ú&.\-]+\s+(?:(?:d[aeo]s?|e)\s+)?){1,6}"
    r"(?:Ltda\.?|LTDA|S/A|S\.A\.?|EIRELI)(?!\w)"
)
_DUMP_DOU = re.compile(r"Candidato\s+M[ée]dia")
# Sufixo de pessoa jurídica em qualquer contexto (sensível a maiúsculas: "ltda" minúsculo é prosa).
_SUFIXO_SOLTO = re.compile(r"\b(?:Ltda\.?|LTDA|S/A|S\.A\.?|EIRELI)(?!\w)")
_EMAIL = re.compile(r"[\w.+*-]+@([\w-]+(?:\.[\w-]+)+)")
_DOMINIOS_OFICIAIS = (".gov.br", ".leg.br", ".jus.br", ".mp.br")
_OAB = re.compile(r"\bOAB\b[^\n]{0,12}?(?:\b[A-Z]{2}\b|\d)")
_H = r"[^\S\n]"  # espaço horizontal (inclui \xa0), sem quebra de linha
_PARTE = re.compile(
    rf"^(?:{_H}|[>|*#_-])*(?:interessado|consulente|recorrente|recorrido|requerente|impugnante"
    rf"|autuado|sujeito\s+passivo|advogado|procurador|raz[ãa]o\s+social)"
    rf"(?:{_H}|[*|_])*[:\-–—](?:{_H}|[*|])*([^\n]*)$",
    re.IGNORECASE | re.MULTILINE,
)
_RAZAO = re.compile(r"(?<!\w)(?:[A-ZÀ-Ú][A-ZÀ-Ú&\-]{1,}\s+){1,8}(?:LTDA|EIRELI|S/?A|S\.A\.)(?!\w)")
_CF_DF = re.compile(r"^[^\n]*\bCF\s*/?\s*DF\b[^\n]*\d[^\n]*$", re.MULTILINE)


class CsvAcimaDoTeto(Exception):
    """O CSV (ou o gzip) passaria do teto de bytes; a saída parcial é removida, nada é truncado."""


def _jsonl(caminho: Path):
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                yield json.loads(linha)


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def _cpf_real(valor: str) -> bool:
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) != 11 or not valor.replace(".", "").replace("-", "").isdigit():
        return False  # máscara (X, *, #) ou não é CPF completo: placeholder
    return len(set(digitos)) > 1 and not digitos.startswith("1234567890")


def _cnpj_real(valor: str) -> bool:
    digitos = re.sub(r"\D", "", valor)
    if re.search(r"[^\d./-]", valor) or len(digitos) not in (14, 15):
        return False  # máscara (X, *, #) ou não é CNPJ: placeholder
    return len(set(digitos)) > 1


def _parte_preenchida(texto: str) -> bool:
    for m in _PARTE.finditer(texto):
        valor = m.group(1).strip(" \t\xa0*|_")
        if re.search(r"[^\W\d_]{2}", valor):
            return True
    return False


def regra_conteudo(
    titulo: str, texto: str, natureza: str | None = None, misto: bool | None = None
) -> str | None:
    """Nome da primeira regra que casa no título ou no texto. Nunca devolve o valor casado."""
    aplicar_misto = misto if misto is not None else natureza in NATUREZAS_MISTO
    for trecho in (titulo, texto):
        if any(_cpf_real(m.group(1)) for m in _CPF.finditer(trecho)) or any(
            _cpf_real(m.group(1)) for m in _CPF_NU.finditer(trecho)
        ):
            return "cpf"
        if any(_cnpj_real(m.group(1)) for m in _CNPJ.finditer(trecho)) or any(
            _cnpj_real(m.group(1)) for m in _CNPJ_NU.finditer(trecho)
        ):
            return "cnpj"
        if any(
            not m.group(1).lower().endswith(_DOMINIOS_OFICIAIS) for m in _EMAIL.finditer(trecho)
        ):
            return "email"
        if _OAB.search(trecho):
            return "oab"
        if _parte_preenchida(trecho):
            return "parte"
        if _RAZAO.search(trecho):
            return "razao_social"
        if aplicar_misto and (_MISTO.search(trecho) or _SUFIXO_SOLTO.search(trecho)):
            return "razao_social_misto"
        if _DUMP_DOU.search(trecho):
            return "dump_dou"
        if _CF_DF.search(trecho):
            return "cf_df"
    return None


_HOST = re.compile(r"https?://[^/\s]+")


def _ato_legal(ocorrencia: dict) -> bool:
    # O host sai da busca: "in.gov.br" não pode fazer uma página do portal passar por IN.
    texto = _HOST.sub(" ", f"{ocorrencia['titulo']} {ocorrencia['chave_origem']}")
    return bool(_ATO_LEGAL.search(_sem_acento(texto)))


def _permitida(ocorrencia: dict, publico: bool) -> bool:
    natureza = ocorrencia["natureza"]
    if publico and (natureza in NATUREZAS_EXCLUIDAS_PUBLICO or natureza.startswith("diario_")):
        return False
    permitidas = NATUREZAS_PUBLICO if publico else NATUREZAS_PERMITIDAS
    if natureza in permitidas:
        return True
    return natureza in NATUREZAS_CONDICIONAIS and _ato_legal(ocorrencia)


def _motivo_exclusao(ocorrencias: list[dict], publico: bool = False) -> str | None:
    """Documento entra só se todas as ocorrências da versão forem permitidas."""
    if any(o["frente"].startswith("cnpj") for o in ocorrencias):
        return "frente_cnpj"
    for o in ocorrencias:
        if not _permitida(o, publico):
            return o["natureza"]
    return None


def _titulo_manifesto(titulo: str, motivo: str) -> str:
    """Título que sai no manifesto. Omitido quando o documento caiu por regra de conteúdo
    (é aí que ficaria o dado casado) ou quando o próprio título casa alguma regra."""
    if motivo.startswith("regra:") or motivo == "revisao_manual":
        return "[omitido]"
    return "[omitido]" if regra_conteudo(titulo, "", misto=True) else titulo


def _nome_manifesto(saida: Path, publico: bool) -> str:
    if publico and saida.name.endswith(".csv"):
        return saida.name[: -len(".csv")] + ".manifesto.json"
    return saida.name + ".manifesto.json"


def _comprimir(origem: Path, teto_gz: int) -> tuple[Path, int, str]:
    """gzip nível 9, sem data nem nome no cabeçalho (saída reproduzível). Aborta acima do teto."""
    destino = origem.with_name(origem.name + ".gz")
    try:
        with open(origem, "rb") as fi, open(destino, "wb") as fo:
            with gzip.GzipFile(filename="", mode="wb", fileobj=fo, mtime=0, compresslevel=9) as fz:
                shutil.copyfileobj(fi, fz)
        tamanho = destino.stat().st_size
        if tamanho > teto_gz:
            raise CsvAcimaDoTeto(f"gzip com {tamanho} bytes passa do teto de {teto_gz}.")
        sha = hashlib.sha256(destino.read_bytes()).hexdigest()
    except BaseException:
        destino.unlink(missing_ok=True)
        origem.unlink(missing_ok=True)
        raise
    origem.unlink()
    return destino, tamanho, sha


def gerar_recorte(
    run: Path,
    saida: Path,
    teto_bytes: int = TETO_BYTES,
    publico: bool = False,
    teto_gz_bytes: int = TETO_GZ_BYTES,
    revisao_manual: frozenset[str] | None = None,
) -> dict:
    run = Path(run)
    saida = Path(saida)
    if revisao_manual is None:
        revisao_manual = frozenset(json.loads(REVISAO_MANUAL_PATH.read_text(encoding="utf-8")))
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
    detalhe: list[dict] = []

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
                motivo = "sem_texto" if caminho_texto is None else _motivo_exclusao(ocs, publico)
                texto = None
                if motivo is None:
                    texto = caminho_texto.read_bytes().decode("utf-8")
                    if publico and nucleo["documento_id"] in revisao_manual:
                        motivo = "revisao_manual"
                    elif publico:
                        regra = regra_conteudo(ocs[0]["titulo"], texto, ocs[0]["natureza"])
                        motivo = f"regra:{regra}" if regra else None
                if motivo:
                    tamanho = caminho_texto.stat().st_size if caminho_texto else 0
                    registro = excluidos.setdefault(motivo, {"documentos": 0, "bytes_texto": 0})
                    registro["documentos"] += 1
                    registro["bytes_texto"] += tamanho
                    if motivo in NATUREZAS_CONDICIONAIS:
                        condicionais_excluidos.append(
                            {
                                "natureza": motivo,
                                "titulo": _titulo_manifesto(ocs[0]["titulo"], motivo),
                                "chave_origem": ocs[0]["chave_origem"],
                            }
                        )
                    if publico:
                        detalhe.append(
                            {
                                "documento_id": nucleo["documento_id"],
                                "titulo": _titulo_manifesto(ocs[0]["titulo"], motivo),
                                "natureza": ocs[0]["natureza"],
                                "regra": motivo,
                            }
                        )
                    continue

                rep = ocs[0]
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

    gz: dict = {}
    if publico:
        destino, gz_bytes, gz_sha = _comprimir(saida, teto_gz_bytes)
        gz = {"gz": destino.name, "gz_bytes": gz_bytes, "gz_sha256": gz_sha}

    manifesto = {
        "run": run.name if publico else str(run),
        "saida": saida.name if publico else str(saida),
        "publico": publico,
        "colunas": list(COLUNAS),
        "naturezas_permitidas": sorted(NATUREZAS_PUBLICO if publico else NATUREZAS_PERMITIDAS),
        "linhas": linhas,
        "bytes": total,
        "sha256": sha.hexdigest(),
        "teto_bytes": teto_bytes,
        "contagens_por_natureza": dict(por_natureza),
        "bytes_texto_por_natureza": dict(bytes_por_natureza),
        "excluidos": excluidos,
        "condicionais_excluidos": condicionais_excluidos,
    }
    if publico:
        manifesto |= gz | {
            "regras_conteudo": REGRAS_CONTEUDO,
            "teto_gz_bytes": teto_gz_bytes,
            "excluidos_detalhe": detalhe,
        }
    saida.with_name(_nome_manifesto(saida, publico)).write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifesto


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exporta o recorte RAG v1 do refino para CSV.")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--saida", required=True, type=Path)
    parser.add_argument("--publico", action="store_true", help="filtro público, gzip e manifesto")
    args = parser.parse_args(argv)
    try:
        manifesto = gerar_recorte(args.run, args.saida, publico=args.publico)
    except CsvAcimaDoTeto as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"linhas: {manifesto['linhas']} bytes: {manifesto['bytes']}")
    print(f"sha256: {manifesto['sha256']}")
    for natureza, n in sorted(manifesto["contagens_por_natureza"].items()):
        print(f"incluido {natureza}: {n}")
    for motivo, dados in sorted(manifesto["excluidos"].items()):
        print(f"excluido {motivo}: {dados['documentos']} docs, {dados['bytes_texto']} bytes")
    if args.publico:
        print(f"gz: {manifesto['gz']} bytes: {manifesto['gz_bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
