"""Limpeza de HTML de legislação.

Separa o conteúdo riscado (``<strike>``) do texto vigente e converte o HTML em
texto puro. Links viram ``[texto](url)``; nenhuma outra tag HTML sobrevive.

Uso:
    python -m backend.cleaning.limpeza_html lei.html [outras.html ...] -o saida/
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

DEFAULT_STRIKE_TAGS = ("strike",)
DROP_TAGS = {"script", "style", "noscript", "head", "title", "meta", "link"}
BLOCK_TAGS = {
    "p", "div", "dir", "ul", "ol", "li", "blockquote", "pre", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "center", "body", "html",
    "dl", "dt", "dd", "hr", "address", "fieldset", "form",
}
CELL_TAGS = {"td", "th"}


@dataclass
class ResultadoLimpeza:
    limpo: str
    removido: str
    trechos_removidos: int


def decode_html(raw: bytes) -> str:
    """Decodifica bytes de HTML: UTF-8 estrito, senão charset declarado, senão cp1252."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    head = raw[:4096].decode("ascii", errors="ignore")
    match = re.search(r"charset=[\"']?([\w-]+)", head, re.I)
    for enc in (match.group(1) if match else None, "cp1252", "latin-1"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _is_strike(node: Tag, strike_tags: tuple[str, ...]) -> bool:
    return node.name in strike_tags


def _render(node, base_url: str | None, out: list[str]) -> None:
    """Renderiza ``node`` em texto puro, acumulando pedaços em ``out``."""
    if isinstance(node, NavigableString):
        if type(node).__name__ in ("Comment", "Doctype", "CData", "ProcessingInstruction", "Declaration"):
            return
        out.append(re.sub(r"[ \t\r\n\xa0]+", " ", str(node)))
        return
    if not isinstance(node, Tag) or node.name in DROP_TAGS:
        return
    name = node.name
    if name == "br":
        out.append("\n")
        return
    if name == "a" and node.get("href"):
        inner: list[str] = []
        for child in node.children:
            _render(child, base_url, inner)
        label = _normalize_inline("".join(inner))
        href = node["href"].strip()
        if base_url and not href.startswith("#"):
            href = urljoin(base_url, href)
        if label and href:
            out.append(f"[{label}]({href})")
        else:
            out.append(label)
        return
    if name in CELL_TAGS:
        out.append("\t")
    block = name in BLOCK_TAGS
    if block:
        out.append("\n")
    for child in node.children:
        _render(child, base_url, out)
    if block:
        out.append("\n")


def _normalize_inline(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _finalize(pieces: list[str]) -> str:
    text = "".join(pieces).replace("\r", "")
    lines = []
    for line in text.split("\n"):
        if "\t" in line:
            cells = [_normalize_inline(c) for c in line.split("\t")]
            line = " | ".join(c for c in cells if c)
        else:
            line = _normalize_inline(line)
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n" if text.strip() else ""


def limpar_html(
    html: str | bytes,
    *,
    strike_tags: tuple[str, ...] = DEFAULT_STRIKE_TAGS,
    base_url: str | None = None,
) -> ResultadoLimpeza:
    """Retorna o texto vigente (sem strike) e o texto removido (conteúdo de strike).

    ``strike_tags`` define quais tags são tratadas como texto riscado (padrão: apenas
    ``strike``). Strikes aninhados contam como um único trecho removido.
    """
    if isinstance(html, bytes):
        html = decode_html(html)
    soup = BeautifulSoup(html, "html.parser")

    # Só o strike mais externo; os aninhados vão junto com ele.
    outer = [
        n for n in soup.find_all(list(strike_tags))
        if not any(_is_strike(p, strike_tags) for p in n.parents if isinstance(p, Tag))
    ]

    removidos: list[str] = []
    for node in outer:
        pieces: list[str] = []
        _render(node, base_url, pieces)
        text = _finalize(pieces).strip()
        if text:
            removidos.append(text)
        node.decompose()

    pieces = []
    _render(soup, base_url, pieces)
    return ResultadoLimpeza(
        limpo=_finalize(pieces),
        removido=("\n\n".join(removidos) + "\n") if removidos else "",
        trechos_removidos=len(removidos),
    )


def processar_arquivo(
    origem: Path,
    destino: Path,
    *,
    strike_tags: tuple[str, ...] = DEFAULT_STRIKE_TAGS,
    base_url: str | None = None,
) -> tuple[Path, Path, ResultadoLimpeza]:
    """Lê ``origem`` e grava ``<nome>.limpo.md`` e ``<nome>.removido.md`` em ``destino``."""
    resultado = limpar_html(origem.read_bytes(), strike_tags=strike_tags, base_url=base_url)
    destino.mkdir(parents=True, exist_ok=True)
    limpo = destino / f"{origem.stem}.limpo.md"
    removido = destino / f"{origem.stem}.removido.md"
    limpo.write_text(resultado.limpo, encoding="utf-8")
    removido.write_text(resultado.removido, encoding="utf-8")
    return limpo, removido, resultado


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arquivos", nargs="+", type=Path, help="arquivos HTML de entrada")
    ap.add_argument("-o", "--saida", type=Path, required=True, help="diretório de saída")
    ap.add_argument("--tags", default=",".join(DEFAULT_STRIKE_TAGS),
                    help="tags tratadas como riscadas, separadas por vírgula (padrão: strike)")
    ap.add_argument("--base-url", help="URL base para resolver links relativos")
    args = ap.parse_args(argv)
    tags = tuple(t.strip().lower() for t in args.tags.split(",") if t.strip())
    for arq in args.arquivos:
        limpo, removido, r = processar_arquivo(arq, args.saida, strike_tags=tags, base_url=args.base_url)
        print(f"{arq.name}: {r.trechos_removidos} trecho(s) riscado(s) -> {limpo.name}, {removido.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
