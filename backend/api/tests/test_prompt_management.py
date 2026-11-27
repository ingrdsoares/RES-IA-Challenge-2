from types import SimpleNamespace

import pytest
from app.errors import DependencyUnavailable
from app.prompt_management import load_prompt
from langfuse.model import TextPromptClient


def remote_prompt(text, version, name="rag/test"):
    return TextPromptClient(
        SimpleNamespace(
            name=name,
            version=version,
            prompt=text,
            labels=["production"],
            config={},
            tags=[],
            commit_message=None,
        )
    )


def test_gets_production_version_and_compiles(monkeypatch):
    remote = remote_prompt("{{question}}", 7)
    calls = []

    def get_prompt(name, **kwargs):
        calls.append((name, kwargs))
        return remote

    monkeypatch.setattr(
        "app.prompt_management.client", lambda: SimpleNamespace(get_prompt=get_prompt)
    )
    prompt = load_prompt("rag/test", question="pergunta sintética")
    assert prompt.text == "pergunta sintética"
    assert prompt.remote is remote
    assert calls == [("rag/test", {"label": "production", "type": "text"})]


def test_missing_prompt_has_a_safe_error(monkeypatch):
    def get_prompt(*args, **kwargs):
        raise RuntimeError("segredo do transporte")

    monkeypatch.setattr(
        "app.prompt_management.client", lambda: SimpleNamespace(get_prompt=get_prompt)
    )
    with pytest.raises(DependencyUnavailable, match="rag/test") as error:
        load_prompt("rag/test")
    assert "segredo" not in str(error.value)


def test_trace_links_prompt_and_keeps_business_content_out(monkeypatch):
    from contextlib import contextmanager
    from unittest.mock import Mock

    from app.config import Settings
    from app.llm_client import chat

    remote = remote_prompt("INSTRUÇÃO", 3)
    span = Mock()
    start = Mock(return_value=contextmanager(lambda: iter([span]))())
    sdk = SimpleNamespace(get_prompt=lambda *a, **k: remote, start_as_current_observation=start)
    monkeypatch.setattr("app.prompt_management.client", lambda: sdk)
    ollama_client = Mock()
    ollama_client.chat.return_value = SimpleNamespace(
        message=SimpleNamespace(content="RESPOSTA FISCAL"), prompt_eval_count=11, eval_count=7
    )
    prompt = load_prompt("rag/test")
    result = chat(
        Settings(llm_provider="ollama"),
        [{"role": "user", "content": "DOCUMENTO FISCAL"}],
        max_tokens=24,
        ollama_client=ollama_client,
        prompt=prompt,
    )
    assert result.texto == "RESPOSTA FISCAL"
    assert start.call_args.kwargs["prompt"] is remote
    assert set(start.call_args.kwargs) == {"name", "as_type", "model", "metadata", "prompt"}
    span.update.assert_called_once_with(usage_details={"input": 11, "output": 7})


def test_trace_does_not_pass_raw_exception_to_sdk(monkeypatch):
    from contextlib import contextmanager
    from unittest.mock import Mock

    from app.prompt_management import observation

    span = Mock()

    @contextmanager
    def start(**kwargs):
        try:
            yield span
        except Exception:
            pytest.fail("O SDK recebeu uma exceção com conteúdo sensível.")

    sdk = SimpleNamespace(start_as_current_observation=start)
    monkeypatch.setattr("app.prompt_management.client", lambda: sdk)
    with pytest.raises(ValueError, match="CPF sintético"):
        with observation("assistant.test"):
            raise ValueError("CPF sintético")
    span.update.assert_called_once_with(level="ERROR", status_message="ValueError")


def test_rejects_template_missing_required_variable(monkeypatch):
    sdk = SimpleNamespace(get_prompt=lambda *a, **k: remote_prompt("Responda {{question}}", 4))
    monkeypatch.setattr("app.prompt_management.client", lambda: sdk)
    with pytest.raises(DependencyUnavailable, match="rag/test"):
        load_prompt("rag/test", question="pergunta", documents="evidência")


def test_same_scope_keeps_the_prompt_version(monkeypatch):
    from unittest.mock import Mock

    from app.prompt_management import prompt_scope

    get_prompt = Mock(side_effect=[remote_prompt("v1", 1), remote_prompt("v2", 2)])
    monkeypatch.setattr(
        "app.prompt_management.client", lambda: SimpleNamespace(get_prompt=get_prompt)
    )
    with prompt_scope():
        assert load_prompt("rag/test").version == "1"
        assert load_prompt("rag/test").version == "1"
    assert load_prompt("rag/test").version == "2"
    assert get_prompt.call_count == 2


def test_sdk_serves_cached_prompt_and_exports_safe_nested_trace(monkeypatch):
    from unittest.mock import Mock

    import httpx
    from app.prompt_management import observation
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SpanExportResult

    export = Mock(return_value=SpanExportResult.SUCCESS)
    monkeypatch.setattr(
        "langfuse._client.span_processor.OTLPSpanExporter.export",
        export,
    )
    fetch = Mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "rag/test",
                "version": 3,
                "type": "text",
                "prompt": "{{question}}",
                "labels": ["production"],
                "tags": [],
                "config": {},
            },
        )
    )
    with httpx.Client(transport=httpx.MockTransport(fetch)) as http:
        sdk = Langfuse(
            public_key="pk-lf-test",
            secret_key="sk-lf-test",
            base_url="http://langfuse.test",
            httpx_client=http,
            tracer_provider=TracerProvider(),
        )
        monkeypatch.setattr("app.prompt_management.client", lambda: sdk)
        with observation("assistant.execute"):
            prompt = load_prompt("rag/test", question="pergunta privada")
            assert load_prompt("rag/test", question="outra pergunta").version == "3"
            with pytest.raises(ValueError, match="CPF privado"):
                with observation("rag/test", as_type="generation", prompt=prompt.remote):
                    raise ValueError("CPF privado")
        sdk.flush()
        sdk.shutdown()
    fetch.assert_called_once()
    assert "label=production" in str(fetch.call_args.args[0].url)
    spans = [span for call in export.call_args_list for span in call.args[0]]
    generation, trace = sorted(spans, key=lambda span: span.parent is None)
    assert generation.parent.span_id == trace.context.span_id
    attributes = generation.attributes
    assert attributes["langfuse.observation.prompt.name"] == "rag/test"
    assert attributes["langfuse.observation.prompt.version"] == 3
    assert "CPF privado" not in str(attributes)
    assert "pergunta privada" not in str(attributes)
    assert not generation.events
