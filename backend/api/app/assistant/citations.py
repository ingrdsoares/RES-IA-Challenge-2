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
