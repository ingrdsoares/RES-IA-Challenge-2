"""Textos oficiais complementares; coleta não comprova vigência."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import httpx
from bs4 import BeautifulSoup
from .legislacao import _convert

DEFAULT_OUTPUT = Path(__file__).parent / "data" / "legislacao-complementar"
CAMARA = "https://www2.camara.leg.br/legin/fed/"
SOURCES = {}
def _source(key, title, path, identity, *, view="publicacao_original_camara", selector=None, encoding="utf-8"):
    SOURCES[key] = dict(title=title, url=CAMARA + path if not path.startswith("https:") else path,
                        identity=identity, view=view, selector=selector, encoding=encoding)

_source("lc128", "Lei Complementar nº 128, de 19 de dezembro de 2008", "leicom/2008/leicomplementar-128-19-dezembro-2008-584953-publicacaooriginal-107817-pl.html", r"LEI COMPLEMENTAR N[º°o]?\s*128,?\s*DE 19 DE DEZEMBRO DE 2008", selector=".textoNorma")
_source("lc147", "Lei Complementar nº 147, de 7 de agosto de 2014", "leicom/2014/leicomplementar-147-7-agosto-2014-779146-publicacaooriginal-144700-pl.html", r"LEI COMPLEMENTAR N[º°o]?\s*147,?\s*DE 7 DE AGOSTO DE 2014", selector=".textoNorma")
_source("lc155", "Lei Complementar nº 155, de 27 de outubro de 2016", "leicom/2016/leicomplementar-155-27-outubro-2016-783850-publicacaooriginal-151329-pl.html", r"LEI COMPLEMENTAR N[º°o]?\s*155,?\s*DE 27 DE OUTUBRO DE 2016", selector=".textoNorma")
_source("lc188", "Lei Complementar nº 188, de 31 de dezembro de 2021", "leicom/2021/leicomplementar-188-31-dezembro-2021-792195-publicacaooriginal-164275-pl.html", r"LEI COMPLEMENTAR N[º°o]?\s*188,?\s*DE 31 DE DEZEMBRO DE 2021", selector=".textoNorma")
_source("lc87", "Lei Complementar nº 87, de 13 de setembro de 1996 — Lei Kandir", "leicom/1996/leicomplementar-87-13-setembro-1996-370965-normaatualizada-pl.html", r"LEI COMPLEMENTAR N[º°o]?\s*87,?\s*DE 13 DE SETEMBRO DE 1996", view="texto_atualizado_camara")
_source("decreto6022", "Decreto nº 6.022, de 22 de janeiro de 2007 — SPED", "decret/2007/decreto-6022-22-janeiro-2007-549814-normaatualizada-pe.html", r"DECRETO N[º°o]?\s*6\.?022,?\s*DE 22 DE JANEIRO DE 2007", view="texto_atualizado_camara")
_source("lei12741", "Lei nº 12.741, de 8 de dezembro de 2012 — Transparência Tributária", "lei/2012/lei-12741-8-dezembro-2012-774745-publicacaooriginal-138316-pl.html", r"LEI N[º°o]?\s*12\.?741,?\s*DE 8 DE DEZEMBRO DE 2012", selector=".textoNorma")
_source("ajuste07_2005", "Ajuste SINIEF 7, de 30 de setembro de 2005 — NF-e", "https://www.confaz.fazenda.gov.br/legislacao/ajustes/2005/AJ_007_05", r"AJUSTE SINIEF (?:N[º°o]?\s*)?0?7(?:/0?5)?,?\s*DE 30 DE SETEMBRO DE 2005", view="texto_confaz", selector="#content-core")
_source("ajuste19_2016", "Ajuste SINIEF 19, de 9 de dezembro de 2016 — NFC-e", "https://www.confaz.fazenda.gov.br/legislacao/ajustes/2016/AJ_019_16", r"AJUSTE SINIEF (?:N[º°o]?\s*)?19(?:/16)?,?\s*DE 9 DE DEZEMBRO DE 2016", view="texto_confaz", selector="#content-core")

UNIT = re.compile(r"^(Art\.\s*\d+(?:[º°o])?(?:-[A-Z]+)?|Cláusula\s+[\wªº]+(?:[ -]+[\wªº]+){0,2})", re.I)
def parse(source, raw):
    info = SOURCES[source]
    soup = BeautifulSoup(raw.decode(info["encoding"] + ("-sig" if info["encoding"] == "utf-8" else "")), "html.parser")
    content = soup.select_one(info["selector"]) if info["selector"] else soup
    if content is None:
        raise ValueError("Bloco normativo ausente")
    plain = " ".join(soup.get_text(" ", strip=True).split())
    # Cabeçalho deve identificar a própria norma antes do primeiro dispositivo.
    prefix = re.split(r"Art\.\s*1[º°o]?|Cláusula primeira", plain, maxsplit=1, flags=re.I)[0]
    if not re.search(info["identity"], prefix, re.I):
        raise ValueError("Identidade da norma divergente")
    if info["selector"] == ".textoNorma":
        # Os <dir> são redações de outras normas transcritas pela lei alteradora.
        # Isolá-los evita colar o Art. seguinte e criar títulos para artigos citados.
        for block in content.find_all("dir"):
            block.name = "blockquote"
        markdown = _convert(str(content), info["url"])
        markdown, count = re.subn(r"(?m)^[ \t\u00a0]*(Art\.\s*\d+(?:[º°o])?(?:-[A-Z]+)?\.?)(?=\s)",
                                 lambda m: "## " + m[1] + "\n\n" + m[1], markdown)
        if not count:
            raise ValueError("Norma sem dispositivos reconhecíveis")
        return markdown
    count = 0
    for block in list(content.find_all(["p", "div"])):
        if block.find(["p", "div"]) or block.find_parent("table"):
            continue
        text = " ".join(block.get_text(" ", strip=True).split())
        match = UNIT.match(text)
        if match:
            heading = soup.new_tag("h2")
            heading.string = match.group(1) if text.lower().startswith("art") else text.split(" ", 2)[0] + " " + text.split(" ", 2)[1]
            block.insert_before(heading)
            count += 1
    if not count:
        raise ValueError("Norma sem dispositivos reconhecíveis")
    markdown = _convert(str(content), info["url"])
    return markdown

def ingest(source, raw, output=DEFAULT_OUTPUT):
    body = parse(source, raw)
    info = SOURCES[source]
    digest = hashlib.sha256(raw).hexdigest()
    target = Path(output) / source / digest
    result = target / "legislacao.md"
    if target.exists():
        try:
            meta = json.loads((target / "metadados.json").read_bytes())
            valid = (meta["sha256"] == digest and meta["source_url"] == info["url"]
                     and meta["source_id"] == source)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError("Versão existente incompleta ou divergente") from exc
        if not valid or (target / "original.html").read_bytes() != raw or not result.is_file():
            raise ValueError("Versão existente incompleta ou divergente")
        return result
    meta = dict(source_id=source, source_url=info["url"], coletado_em=datetime.now(timezone.utc).isoformat(), sha256=digest, status="coletado", visao=info["view"], camada="A", vigencia="nao_verificada", revisao_humana="pendente")
    content = "---\n" + "\n".join(f"{k}: {v}" for k,v in meta.items()) + "\n---\n\n# " + info["title"] + "\n\n[Arquivo original](original.html)\n\n> Coleta para pesquisa. Vigência não verificada; revisão humana pendente. Leis alteradoras não equivalem à LC 123 consolidada.\n\n" + body + "\n"
    target.mkdir(parents=True)
    (target / "original.html").write_bytes(raw)
    result.write_bytes(content.encode("utf-8"))
    (target / "metadados.json").write_bytes(json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))
    return result

def collect(output=DEFAULT_OUTPUT, sources=None, client=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with httpx.Client(timeout=60, follow_redirects=True) if client is None else client as session:
        for source in sources or SOURCES:
            try:
                response = session.get(SOURCES[source]["url"])
                response.raise_for_status()
                result = ingest(source, response.content, output)
                meta = json.loads((result.parent / "metadados.json").read_bytes())
                records.append(dict(meta, caminho=str(result.relative_to(output)).replace("\\", "/")))
            except (httpx.HTTPError, ValueError, OSError, UnicodeError) as exc:
                records.append(dict(source_id=source, source_url=SOURCES[source]["url"], status="falha", erro=str(exc)))
    manifest = dict(total=len(records), coletados=sum(r["status"]=="coletado" for r in records), falhas=sum(r["status"]=="falha" for r in records), documentos=records)
    (output / "manifesto.json").write_bytes(json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    (output / "indice.md").write_bytes(("# Legislação complementar\n\nVigência não verificada; revisão humana pendente.\n\n" + "\n".join(f'- [{r["source_id"]}]({r["caminho"]})' if r["status"]=="coletado" else f'- {r["source_id"]}: FALHA — {r["erro"]}' for r in records) + "\n").encode("utf-8"))
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", choices=["all", *SOURCES], default="all")
    args = parser.parse_args()
    result = collect(args.output, None if args.source == "all" else [args.source])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result["falhas"]))

if __name__ == "__main__":
    raise SystemExit(main())
