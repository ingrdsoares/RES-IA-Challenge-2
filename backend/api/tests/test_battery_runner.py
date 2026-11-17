import pytest
from app.config import Settings


def test_runner_records_effective_window_and_rejects_mixed_resume():
    from scripts.evaluate_agent_flows import evaluation_parameters, validate_resume

    maximum = evaluation_parameters(Settings(num_ctx=40960), b"[]")
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
