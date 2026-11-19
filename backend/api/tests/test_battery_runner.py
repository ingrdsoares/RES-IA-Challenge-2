import pytest
from app.config import Settings


def test_runner_records_effective_window_and_rejects_mixed_resume():
    from scripts.evaluate_agent_flows import evaluation_parameters, validate_resume

    # Same profile the CLI builds for --num-ctx 40960 (window and retrieved chars together).
    maximum = evaluation_parameters(Settings(num_ctx=40960, max_context_chars=40960), b"[]")
    assert maximum["num_ctx"] == 40960
    assert maximum["max_context_chars"] == 40960
    previous = {**maximum, "num_ctx": 8192}
    with pytest.raises(ValueError):
        validate_resume({"metadata": {"parameters": previous}, "cases": [{"id": "A01"}]}, maximum)
    validate_resume({"metadata": {"parameters": maximum}, "cases": [{"id": "A01"}]}, maximum)


def test_runner_refuses_unversioned_baseline_as_resume_target():
    from scripts.evaluate_agent_flows import evaluation_parameters, validate_resume

    parameters = evaluation_parameters(Settings(), b"[]")
    with pytest.raises(ValueError):
        validate_resume({"metadata": {}, "cases": [{"id": "A01"}]}, parameters)
    validate_resume({"metadata": {}, "cases": []}, parameters)


def test_evaluation_thinking_is_forwarded_without_changing_generation_options():
    from scripts.evaluate_agent_flows import EvaluationClient

    class Client:
        def chat(self, **kwargs):
            self.received = kwargs
            return "response"

    wrapped = Client()
    client = EvaluationClient(wrapped, thinking=True)
    assert client.chat(think=False, options={"num_ctx": 16384, "num_predict": 4096}) == "response"
    assert wrapped.received == {"think": True, "options": {"num_ctx": 16384, "num_predict": 4096}}


def test_resume_rejects_changed_thinking_mode():
    from scripts.evaluate_agent_flows import evaluation_parameters, validate_resume

    settings = Settings(num_ctx=16384)
    parameters = evaluation_parameters(settings, b"[]", thinking=True)
    assert parameters["thinking"] is True
    with pytest.raises(ValueError):
        validate_resume(
            {"metadata": {"parameters": parameters}, "cases": [{"id": "A01"}]},
            evaluation_parameters(settings, b"[]", thinking=False),
        )


def test_runner_records_backend_retrieval_parameters():
    from scripts.evaluate_agent_flows import evaluation_parameters

    settings = Settings(top_k=8, score_threshold=0.5, reranker_url="http://localhost:18080")
    parameters = evaluation_parameters(settings, b"[]")
    assert parameters["top_k"] == 8
    assert parameters["score_threshold"] == 0.5
    assert parameters["retrieval_mode"] == "backend_hybrid_reranker"
    assert parameters["reranker_url"] == "http://localhost:18080/"


def test_evaluation_reranker_fails_explicitly_instead_of_silent_fallback():
    import httpx

    from scripts.evaluate_agent_flows import VerifiedRerankerClient

    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        audited = VerifiedRerankerClient(client, [])
        with pytest.raises(RuntimeError, match="reranker"):
            audited.post("http://reranker/rerank", json={"question": "q", "texts": ["source"]})


def test_evaluation_reranker_records_real_success():
    import httpx

    from scripts.evaluate_agent_flows import VerifiedRerankerClient

    audits = []
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"scores": [2.5]}))
    ) as client:
        audited = VerifiedRerankerClient(client, audits)
        assert audited.post(
            "http://reranker/rerank", json={"question": "q", "texts": ["source"]}
        ).json()["scores"] == [2.5]
    assert audits[0]["texts"] == 1 and audits[0]["status"] == "succeeded"


def test_backend_legal_retains_normal_retrieval_when_only_validity_is_overridden(monkeypatch):
    from contextlib import nullcontext
    from unittest.mock import MagicMock

    import app.assistant.agents.tools as module

    settings = Settings()
    captured = {}
    monkeypatch.setattr(module, "QdrantClient", lambda **kwargs: MagicMock())
    monkeypatch.setattr(module, "LocalModels", lambda settings: MagicMock())
    monkeypatch.setattr(module, "require_company", lambda *args: None)
    monkeypatch.setattr(module, "active_collection", lambda db: "hybrid-active")

    def retrieve(*args, **kwargs):
        captured.update(kwargs)
        captured["limit"] = args[5]
        captured["threshold"] = args[6]
        return []

    monkeypatch.setattr(module, "retrieve_legal", retrieve)
    tools = module.AgentTools(lambda: nullcontext(None), "owner", "company", {}, settings)
    reranker = MagicMock()
    tools.legal("question", ignore_validity_for_test=True, reranker=reranker)
    assert captured == {
        "hybrid_collection": "hybrid-active",
        "reranker": reranker,
        "ignore_validity_for_test": True,
        "limit": settings.top_k,
        "threshold": settings.score_threshold,
    }


def test_queued_case_is_retried_until_terminal():
    from scripts.evaluate_agent_flows import execute_until_terminal

    statuses = iter([{"status": "queued"}, {"status": "succeeded"}])
    calls = []
    result = execute_until_terminal(lambda: calls.append(True), lambda: next(statuses), 3)
    assert result["status"] == "succeeded" and len(calls) == 2


def test_retries_are_bounded_without_calling_queued_a_success():
    from scripts.evaluate_agent_flows import execute_until_terminal

    calls = []
    result = execute_until_terminal(lambda: calls.append(True), lambda: {"status": "queued"}, 3)
    assert result["status"] == "queued" and len(calls) == 3


def test_resume_reprocesses_nonterminal_ids_and_replaces_saved_record():
    from scripts.evaluate_agent_flows import completed_ids, record_case

    result = {
        "metadata": {},
        "cases": [
            {"id": "A01", "operation": {"status": "queued"}},
            {"id": "A02", "operation": {"status": "failed"}},
        ],
    }
    assert completed_ids(result) == {"A02"}
    record_case(result, {"id": "A01", "operation": {"status": "succeeded"}})
    assert len(result["cases"]) == 2
    assert completed_ids(result) == {"A01", "A02"}
    assert result["metadata"]["prior_nonterminal_records"][0]["operation"]["status"] == "queued"
