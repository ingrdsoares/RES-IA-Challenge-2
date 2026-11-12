"""Planilha para revisão fiscal independente (preenchimento externo)."""

VEREDITOS = ["correta", "recusa adequada", "parcial", "errada", "recusa indevida"]
INSTRUCOES_REVISAO = [
    {"orientação": "Preencha veredito, base_legal_conferida e comentario sem consultar o RAG."},
    {"orientação": "veredito aceita: " + ", ".join(VEREDITOS)},
]


def _fonte(s, limite=300):
    texto = " ".join((s.get("text") or "").split())
    titulo = s.get("title") or s.get("source") or ""
    return f"{titulo}: {texto[:limite]}"


def linhas_revisao(snapshot):
    """Uma linha por pergunta (primeira tentativa); o revisor preenche as 3 últimas colunas."""
    primeiras = {}
    for r in sorted(snapshot.results, key=lambda r: r.attempt.repeat_index):
        primeiras.setdefault(r.case.id, r)
    return [
        {
            "id": r.case.id,
            "categoria": r.case.category,
            "pergunta": r.case.question,
            "resposta_referencia": r.case.ground_truth,
            "fontes_esperadas": ", ".join(map(str, r.case.expected_sources)),
            "status_sistema": r.attempt.rag_status,
            "resposta_sistema": r.attempt.answer,
            "fontes_citadas": "\n".join(
                f"[{i}] {_fonte(s)}" for i, s in enumerate(r.attempt.sources, 1)
            ),
            "veredito": None,
            "base_legal_conferida": None,
            "comentario": None,
        }
        for r in primeiras.values()
    ]
