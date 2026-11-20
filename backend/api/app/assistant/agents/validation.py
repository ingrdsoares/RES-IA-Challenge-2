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


def render_answer(final, support, has_fiscal, has_legal=False):
    text = final["answer"]
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
    return text
