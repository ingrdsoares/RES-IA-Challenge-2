from datetime import date
from uuid import uuid4

import pytest
from qdrant_client import QdrantClient
from test_access import csrf
from test_conversations import conversation


@pytest.mark.parametrize(
    "mode", ["valid", "invented", "timeout", "too_many_steps", "other_jurisdiction", "mixed_retry"]
)
def test_assistant_persists_sources_once(client, mode):
    from app.assistant.orchestrator import answer_message
    from app.jobs.worker import execute
    from app.legal.index import index_version
    from app.legal.models import Norm, NormVersion
    from app.legal.normalize import normalize

    company, chat = conversation(client)
    response = client.post(
        "/conversas/" + chat["id"] + "/mensagens",
        json={
            "text": "Paguei a guia em 2026-10? Qual é a regra?"
            if mode == "mixed_retry"
            else "O que é MEI?"
        },
        headers={**csrf(client), "Idempotency-Key": "answer"},
    )
    from uuid import UUID

    operation_id = UUID(response.json()["operation_id"])
    index = QdrantClient(":memory:")
    with client.app.state.db_factory() as db:
        norm = Norm(document_key="test")
        db.add(norm)
        db.flush()
        version = NormVersion(
            document_id=norm.id,
            version_label="v1",
            title="Teste",
            authority="Teste",
            jurisdiction="BR-SP" if mode == "other_jurisdiction" else "BR",
            norm_type="lei",
            subjects=[],
            official_url="https://example.org/law",
            effective_from=date(2020, 1, 1),
            checksum="a" * 64,
            metadata_hash="b" * 64,
            original_key="test/original.md",
            json_key="test/doc.json",
            anchors=[],
            media_type="text/markdown",
            status="ready",
        )
        db.add(version)
        db.flush()
        document = normalize(b"Art. 1 Test rule.", "text/markdown")
        version.anchors = [document.sections[0].anchor_id]
        index_version(index, version, document, lambda text: [1.0, 0.0], 2)
        db.commit()

    attempts = []

    def generate(prompt):
        attempts.append(prompt)
        if mode == "mixed_retry" and len(attempts) == 1:
            raise TimeoutError("transient")
        if mode == "timeout":
            raise TimeoutError("private internal details")
        return {
            "answer": "Explicacao [2]" if mode == "invented" else "Explicacao [1]",
            "cited_indices": [2] if mode == "invented" else [1],
            "next_steps": ["Conferir a fonte"] * (4 if mode == "too_many_steps" else 1),
        }

    def handler(db, operation):
        return answer_message(
            db,
            operation,
            settings=client.app.state.settings,
            index=index,
            embed=lambda text: [1.0, 0.0],
            generate=generate,
        )

    for _ in range(3):
        execute(client.app.state.db_factory, operation_id, {"assistant.answer": handler})
    messages = client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"]
    operation = client.get("/operacoes/" + str(operation_id)).json()
    if mode == "other_jurisdiction":
        assert len(messages) == 2
        assert messages[-1]["status"] == "insufficient_context"
        assert messages[-1]["citations"] == []
        assert operation["status"] == "succeeded"
    elif mode == "mixed_retry":
        assert len(messages) == 2
        assert len(attempts) == 2
        assert messages[-1]["citations"][0]["version_id"] == str(version.id)
        assert (
            messages[-1]["context"]["fiscal_status"]["obligations"]["verification"] == "unverified"
        )
        assert messages[-1]["next_steps"][0].startswith("Conferir o comprovante")
        stages = operation["result"]["stages"]
        assert any(s["role"] == "sintese" and s["status"] == "failed" for s in stages)
        assert [s["role"] for s in stages[-5:]] == [
            "supervisor",
            "diagnostico_fiscal",
            "juridico",
            "sintese",
            "planejamento",
        ]
    elif mode == "valid":
        assert len(messages) == 2
        assert messages[1]["role"] == "assistant"
        assert messages[1]["citations"][0]["version_id"] == str(version.id)
        assert messages[1]["next_steps"] == ["Conferir a fonte"]
        assert operation["status"] == "succeeded"
    else:
        assert len(messages) == 1
        assert messages[0]["status"] == "failed"
        assert operation["status"] == "failed"
        assert "private internal details" not in str(operation)
    index.close()


def test_empty_context_abstains_and_later_job_waits(client):
    from uuid import UUID

    from app.assistant.orchestrator import answer_message
    from app.jobs.models import Operation
    from app.jobs.worker import execute

    company, chat = conversation(client)
    url = "/conversas/" + chat["id"] + "/mensagens"
    operations = [
        UUID(
            client.post(
                url,
                json={"text": f"Pergunta {i}"},
                headers={**csrf(client), "Idempotency-Key": str(i)},
            ).json()["operation_id"]
        )
        for i in range(2)
    ]
    index = QdrantClient(":memory:")
    calls = []

    def handler(db, operation):
        return answer_message(
            db,
            operation,
            index=index,
            embed=lambda text: [1.0, 0.0],
            generate=lambda prompt: calls.append(prompt),
        )

    execute(client.app.state.db_factory, operations[1], {"assistant.answer": handler})
    with client.app.state.db_factory() as db:
        assert db.get(Operation, operations[1]).attempts == 0
        assert db.get(Operation, operations[1]).status == "queued"
    for operation in operations:
        execute(client.app.state.db_factory, operation, {"assistant.answer": handler})
    messages = client.get(url).json()["items"]
    answers = [message for message in messages if message["role"] == "assistant"]
    assert len(answers) == 2
    assert all(answer["status"] == "insufficient_context" for answer in answers)
    assert calls == []
    index.close()


@pytest.mark.integration
def test_real_ollama_structured_response(client):
    import os

    if not os.getenv("OLLAMA_TEST_URL"):
        pytest.skip("requires OLLAMA_TEST_URL")
    from uuid import UUID

    from app.assistant.orchestrator import answer_message
    from app.jobs.worker import execute
    from app.legal.index import index_version
    from app.legal.models import Norm, NormVersion
    from app.legal.normalize import normalize
    from app.models import LocalModels

    company, chat = conversation(client)
    operation_id = UUID(
        client.post(
            "/conversas/" + chat["id"] + "/mensagens",
            json={"text": "Como a biblioteca demonstrativa organiza os documentos?"},
            headers={**csrf(client), "Idempotency-Key": "real"},
        ).json()["operation_id"]
    )
    settings = client.app.state.settings.model_copy(
        update={"ollama_url": os.environ["OLLAMA_TEST_URL"]}
    )
    model = LocalModels(settings)
    index = QdrantClient(":memory:")
    try:
        with client.app.state.db_factory() as db:
            norm = Norm(document_key="smoke")
            db.add(norm)
            db.flush()
            document = normalize(
                "Art. 1 A biblioteca demonstrativa organiza documentos por assunto e permite consultar a versão citada na conversa.".encode(),
                "text/markdown",
            )
            version = NormVersion(
                document_id=norm.id,
                version_label="v1",
                title="Documento demonstrativo",
                authority="Teste",
                jurisdiction="BR",
                norm_type="demonstracao",
                subjects=[],
                official_url="https://example.org/test",
                effective_from=date(2020, 1, 1),
                checksum="a" * 64,
                metadata_hash="b" * 64,
                original_key="test/smoke.md",
                json_key="test/smoke.json",
                media_type="text/markdown",
                status="ready",
                anchors=[document.sections[0].anchor_id],
            )
            db.add(version)
            db.flush()
            index_version(
                index,
                version,
                document,
                lambda text: model.client.embed(
                    model=settings.embedding_model, input=text, truncate=False
                ).embeddings[0],
                1024,
            )
            db.commit()
        errors = []

        def real_handler(db, operation):
            try:
                return answer_message(db, operation, settings=settings, index=index)
            except Exception as error:
                errors.append(f"{type(error).__name__}: {error}")
                raise

        execute(client.app.state.db_factory, operation_id, {"assistant.answer": real_handler})
        operation = client.get("/operacoes/" + str(operation_id)).json()
        assert operation["status"] == "succeeded", errors
        messages = client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"]
        assert messages[-1]["status"] == "answered", messages[-1]
        assert messages[-1]["citations"][0]["version_id"] == str(version.id)
    finally:
        model.close()
        index.close()


@pytest.mark.parametrize("answer,expected", [("Texto [1]", 1), ("Texto [1, 2]", 2)])
def test_valid_unused_reference_does_not_reject_grounded_answer(answer, expected):
    from app.assistant.citations import validate_answer_citations

    passages = [{"document_id": "doc", "version_id": "v1", "anchor_id": str(i)} for i in (1, 2)]
    assert len(validate_answer_citations(answer, [1, 2], passages)) == expected


def test_unused_invented_reference_is_rejected():
    from app.assistant.citations import validate_answer_citations

    with pytest.raises(ValueError):
        validate_answer_citations(
            "Texto [1]", [1, 99], [{"document_id": "d", "version_id": "v", "anchor_id": "a"}]
        )


def test_assistente_via_nuvem():
    import json as _json
    from types import SimpleNamespace

    import httpx
    from app.assistant.orchestrator import synthesize
    from app.config import Settings

    rascunho = {"answer": "Resposta [1]", "cited_indices": [1], "next_steps": []}

    def respond(request):
        corpo = _json.loads(request.content)
        assert corpo["response_format"]["type"] == "json_object"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": _json.dumps(rascunho)}}]}
        )

    settings = Settings(llm_provider="google", google_api_key="k", generation_model="gemini-x")
    model = SimpleNamespace(
        client=None, http_client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    db = SimpleNamespace(scalars=lambda query: [])
    user = SimpleNamespace(text="Pergunta", context={}, created_at=date.today(), id=uuid4())
    passages = [
        {"text": "Trecho normativo.", "document_id": "d", "version_id": "v", "anchor_id": "a"}
    ]
    draft, _ = synthesize(db, user, SimpleNamespace(id=uuid4()), passages, settings, model, None)
    assert draft.answer.startswith("Resposta [1]")
