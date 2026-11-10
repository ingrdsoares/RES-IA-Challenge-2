def validate_citations(citations: list[dict], passages: list[dict]) -> list[dict]:
    allowed = {(p["document_id"], p["version_id"], p["anchor_id"]) for p in passages}
    checked = []
    for citation in citations:
        key = (citation.get("document_id"), citation.get("version_id"), citation.get("anchor_id"))
        if key not in allowed:
            raise ValueError("Referência não retornada pelas ferramentas")
        if citation not in checked:
            checked.append(citation)
    return checked


def validate_answer_citations(
    answer: str, declared_indices: list[int], passages: list[dict]
) -> list[dict]:
    import re

    inline = {
        int(number)
        for group in re.findall(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]", answer)
        for number in re.findall(r"\d+", group)
    }
    declared = set(declared_indices)
    if (
        not inline
        or not inline.issubset(declared)
        or any(index < 1 or index > len(passages) for index in declared)
    ):
        raise ValueError("Citações inválidas")
    return validate_citations([passages[index - 1] for index in sorted(inline)], passages)
