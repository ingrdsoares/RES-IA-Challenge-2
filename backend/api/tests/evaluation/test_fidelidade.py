from evaluation.metrics.fidelidade import artigo_esperado, citacao_suportada
from evaluation.reports.revisao import linhas_revisao
from evaluation.schemas import AttemptResult, EvalCase
from evaluation.statistics import agreement
from evaluation.storage import make_manifest  # noqa: F401  (garante import do pacote)

FONTE = {
    "text": "Art. 3º Para os efeitos desta Lei Complementar, considera-se ME a sociedade...",
    "source": "x",
    "title": "Lei Complementar 123/2006",
    "id": 1,
}


def caso(gt="Conforme art. 3º, I, da LC 123/2006, a ME tem limite.", behavior="answer"):
    return EvalCase(
        id="q", category="c", question="Pergunta?", ground_truth=gt, expected_behavior=behavior
    )


def tentativa(answer, sources=(FONTE,), status="answered", n=1):
    return AttemptResult(
        case_id="q",
        repeat_index=n,
        state="success",
        rag_status=status,
        answer=answer,
        sources=list(sources),
    )


def test_artigo_esperado_recuperado_e_ausente():
    assert artigo_esperado(caso(), tentativa("ok")).f1 == 1.0
    assert artigo_esperado(caso(), tentativa("ok", sources=[])).f1 == 0.0
    assert artigo_esperado(caso("Sem artigo."), tentativa("ok")).state == "skipped"
    assert artigo_esperado(caso(behavior="abstain"), tentativa("ok")).state == "skipped"
    assert artigo_esperado(caso(), tentativa("?", [], "needs_clarification")).state == "skipped"


def test_artigo_esperado_formato_lei_artigo_depois():
    gt = "Lei 9.249/1995, art. 15"
    fonte = {"text": "Art. 15. A base de cálculo", "source": "x", "title": "Lei 9.249/1995"}
    assert artigo_esperado(caso(gt), tentativa("ok", [fonte])).f1 == 1.0


def test_citacao_suportada():
    ok = citacao_suportada(caso(), tentativa("Veja art. 3º da LC 123/2006 [1]."))
    assert ok.f1 == 1.0
    ruim = citacao_suportada(caso(), tentativa("Veja art. 99 da LC 123/2006 [1] [4]."))
    assert ruim.f1 == 1 / 3
    assert len(ruim.details["sem_suporte"]) == 2


def test_citacao_na_para_recusa_e_sem_citacao():
    assert (
        citacao_suportada(caso(), tentativa("Sem base.", [], "insufficient_context")).state
        == "skipped"
    )
    assert (
        citacao_suportada(caso(), tentativa("Qual regime?", [], "needs_clarification")).state
        == "skipped"
    )
    assert citacao_suportada(caso(), tentativa("Resposta sem citar.")).state == "skipped"


def test_concordancia_entre_repeticoes():
    class R:
        def __init__(self, a):
            self.case, self.attempt = caso(), a

    rows = [R(tentativa("A", n=1)), R(tentativa("A", n=2)), R(tentativa("B", n=3))]
    (linha,) = agreement(rows)
    assert linha["repeats"] == 3 and abs(linha["answer_agreement"] - 2 / 3) < 1e-9
    assert linha["source_agreement"] == 1.0


def test_planilha_revisao():
    class S:
        class results:
            pass

    class R:
        case, attempt = caso(), tentativa("Resp", status="answered")

    class Snap:
        results = [R()]

    (linha,) = linhas_revisao(Snap())
    assert (
        linha["status_sistema"] == "answered"
        and "Lei Complementar 123/2006" in linha["fontes_citadas"]
    )
    assert linha["veredito"] is None
