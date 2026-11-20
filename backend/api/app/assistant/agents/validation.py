import re


def validate_results(support, legal, fiscal, actions, final):
    used = set()
    for result, prefixes in ((legal, ("legal:",)), (fiscal, ("evidence:", "calculation:"))):
        for claim in result.get("claims", []):
            refs = set(claim["support_ids"])
            if (
                not refs
                or not refs <= support.keys()
                or any(not ref.startswith(prefixes) for ref in refs)
            ):
                raise ValueError("Afirmação sem suporte")
            used |= refs
    for action in actions.get("actions", []):
        refs = set(action["support_ids"])
        if not refs or not refs <= used:
            raise ValueError("Ação sem suporte validado")
        if action.get("deadline_kind") == "normative" and action.get("due_date"):
            # No structured statutory deadline extractor exists yet.
            raise ValueError("Prazo normativo não verificado")
    final_refs = set(final.get("support_ids", []))
    if not final_refs <= used:
        raise ValueError("Síntese sem suporte dos especialistas")
    inline = {
        f"legal:{number}"
        for group in re.findall(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]", final["answer"])
        for number in re.findall(r"\d+", group)
    }
    if inline != {ref for ref in final_refs if ref.startswith("legal:")}:
        raise ValueError("Citações inline inconsistentes")
    if legal.get("claims") and not inline:
        raise ValueError("Síntese jurídica sem citação")
    return final


def align_citations(text: str, legal_refs: list[str]) -> str:
    """Gera ou alinha marcadores inline [n] a partir dos support_ids jurídicos validados."""
    if not legal_refs:
        return text
    legal_numbers = [r.split(":")[1] for r in legal_refs if r.startswith("legal:")]
    if not legal_numbers:
        return text

    matches = list(re.finditer(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]", text))
    if not matches:
        markers = " ".join(f"[{n}]" for n in legal_numbers)
        clean = text.rstrip(".")
        return f"{clean} {markers}." if text.endswith(".") else f"{clean} {markers}"

    # Coleta números distintos citados no texto na ordem de aparição
    cited_nums = []
    for m in matches:
        for n in re.findall(r"\d+", m.group(1)):
            if n not in cited_nums:
                cited_nums.append(n)

    # Mapeia números sequenciais (ex: 1, 2, ...) aos IDs jurídicos reais
    num_map = {}
    for idx, c_num in enumerate(cited_nums):
        if idx < len(legal_numbers):
            num_map[c_num] = legal_numbers[idx]
        else:
            num_map[c_num] = legal_numbers[-1]

    def repl(m):
        nums = re.findall(r"\d+", m.group(1))
        mapped = [num_map.get(n, n) for n in nums]
        return "[" + ", ".join(mapped) + "]"

    new_text = re.sub(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]", repl, text)

    # Garante que todos os números jurídicos foram citados inline
    used_numbers = set(
        re.findall(r"\d+", " ".join(re.findall(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]", new_text)))
    )
    missing = [n for n in legal_numbers if n not in used_numbers]
    if missing:
        missing_markers = " ".join(f"[{n}]" for n in missing)
        clean = new_text.rstrip(".")
        new_text = (
            f"{clean} {missing_markers}."
            if new_text.endswith(".")
            else f"{clean} {missing_markers}"
        )

    return new_text


def render_answer(final, support, has_fiscal, has_legal=False):
    text = final.get("answer", "")
    if has_legal and not final.get("legal_claims") and not has_fiscal:
        return "Não encontrei contexto normativo publicado e vigente suficiente para responder."
    if has_fiscal:
        parts = []
        for key, value in support.items():
            if key.startswith("calculation:"):
                if value["status"] == "calculated":
                    parts.append(
                        f"Valor simulado pelo motor: R$ {value['result']['amount']}. Regra: {value['result']['rule_version']}."
                    )
                else:
                    parts.append(value.get("reason") or value["status"])
        parts.append(
            "Situação fiscal: não verificada oficialmente. Evidências declaradas não comprovam pagamento nem regularidade."
        )
        for claim in final.get("legal_claims", []):
            parts.append(
                claim["text"]
                + " "
                + " ".join(
                    "[" + ref.split(":")[1] + "]"
                    for ref in claim["support_ids"]
                    if ref.startswith("legal:")
                )
            )
        text = "\n".join(parts)
    elif has_legal and final.get("legal_claims"):
        legal_refs = sorted(
            {
                ref
                for claim in final.get("legal_claims", [])
                for ref in claim.get("support_ids", [])
                if ref.startswith("legal:")
            },
            key=lambda r: int(r.split(":")[1]),
        )
        text = align_citations(text, legal_refs)
    return text
