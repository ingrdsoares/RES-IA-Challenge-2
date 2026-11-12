"""Métricas determinísticas de fidelidade às fontes (sem LLM juiz).

- artigo_esperado: fração dos pares (norma, artigo) da ground_truth presentes nas fontes recuperadas.
- citacao_suportada: fração das citações da resposta (pares norma/artigo e marcadores [n])
  que as fontes sustentam. Citação sem suporte é indício de alucinação.
Sem referências para avaliar, ou em recusa/esclarecimento, o resultado é N/A (estado "skipped"),
nunca 0.
"""

import re

from app.citacoes_normas import pares_fontes
from app.normas import artigos_citados

from evaluation.schemas import MetricScore

FIDELIDADE = ["artigo_esperado", "citacao_suportada"]
SEM_RESPOSTA = ("needs_clarification", "insufficient_context", "empty_knowledge_base")
_MARCADOR = re.compile(r"\[(\d{1,3})\]")


def _na(motivo):
    return MetricScore(state="skipped", error=motivo)


def _fracao(achados, total, **details):
    valor = len(achados) / len(total)
    return MetricScore(precision=valor, recall=valor, f1=valor, state="success", details=details)


def artigo_esperado(case, attempt):
    esperados = artigos_citados(case.ground_truth)
    if case.expected_behavior != "answer" or not esperados:
        return _na("sem_referencia_normativa")
    if attempt.state != "success" or attempt.rag_status == "needs_clarification":
        return _na("ineligible_response")
    disponiveis = pares_fontes(attempt.sources)
    achados = [p for p in esperados if p in disponiveis]
    return _fracao(
        achados, esperados, esperados=esperados, ausentes=[p for p in esperados if p not in achados]
    )


def citacao_suportada(case, attempt):
    if attempt.state != "success" or not (attempt.answer or "").strip():
        return _na("ineligible_response")
    if attempt.rag_status in SEM_RESPOSTA:
        return _na("recusa_ou_esclarecimento")
    citados = artigos_citados(attempt.answer)
    marcadores = sorted({int(m) for m in _MARCADOR.findall(attempt.answer)})
    if not citados and not marcadores:
        return _na("sem_citacoes")
    disponiveis = pares_fontes(attempt.sources)
    itens = [("art", p) for p in citados] + [("n", n) for n in marcadores]
    ok = [
        (k, v)
        for k, v in itens
        if (v in disponiveis if k == "art" else 1 <= v <= len(attempt.sources))
    ]
    return _fracao(
        ok, itens, sem_suporte=[v for k, v in itens if (k, v) not in ok], total_citacoes=len(itens)
    )


def fidelidade(row):
    """Pontuações de fidelidade de um ScoredAttempt, calculadas sob demanda (nada persistido)."""
    return {
        "artigo_esperado": artigo_esperado(row.case, row.attempt),
        "citacao_suportada": citacao_suportada(row.case, row.attempt),
    }


def get_score(row, metric):
    return fidelidade(row)[metric] if metric in FIDELIDADE else getattr(row, metric)
