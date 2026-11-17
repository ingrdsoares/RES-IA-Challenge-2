"""Opt-in real Qwen + Qdrant execution using only demonstration documents."""

import os
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_access import csrf
from test_conversations import conversation


@pytest.mark.integration
def test_multiagent_real_qwen(client, monkeypatch):
    if not os.getenv("MULTIAGENT_TEST_URL"):
        pytest.skip("requires MULTIAGENT_TEST_URL and MULTIAGENT_QDRANT_URL")
    from app.assistant.agents.executor import execute_run
    from app.assistant.agents.models import AgentRun, AgentStep
    from app.assistant.agents.tools import AgentTools
    from app.assistant.tools import retrieve_legal
    from app.legal.index import index_version
    from app.legal.models import Norm, NormVersion
    from app.legal.normalize import normalize
    from app.models import LocalModels
    from qdrant_client import QdrantClient

    company, chat = conversation(client)
    settings = client.app.state.settings.model_copy(
        update={
            "ollama_url": os.environ["MULTIAGENT_TEST_URL"],
            "qdrant_url": os.environ["MULTIAGENT_QDRANT_URL"],
        }
    )
    factory = client.app.state.db_factory
    index = QdrantClient(url=str(settings.qdrant_url))
    models = LocalModels(settings)
    collection = "agent_smoke_" + uuid4().hex
    try:
        with factory.begin() as db:
            norm = Norm(document_key=collection)
            db.add(norm)
            db.flush()
            document = normalize(
                "Art. 1 A biblioteca demonstrativa organiza documentos por assunto e conserva a versão citada na conversa.".encode(),
                "text/markdown",
            )
            version = NormVersion(
                document_id=norm.id,
                version_label="demo",
                title="Norma demonstrativa da biblioteca",
                authority="Demonstração",
                jurisdiction="BR",
                norm_type="demonstracao",
                subjects=[],
                official_url="https://example.org/demo",
                effective_from=date(2020, 1, 1),
                checksum="a" * 64,
                metadata_hash="b" * 64,
                original_key="demo/original.md",
                json_key="demo/document.json",
                media_type="text/markdown",
                status="ready",
                anchors=[section.anchor_id for section in document.sections],
            )
            db.add(version)
            db.flush()
            index_version(
                index,
                version,
                document,
                lambda text: models.client.embed(
                    model=settings.embedding_model, input=text, truncate=False
                ).embeddings[0],
                1024,
                collection=collection,
            )
        response = client.post(
            "/conversas/" + chat["id"] + "/mensagens",
            json={
                "text": "Segundo a norma demonstrativa, como a biblioteca organiza documentos? Considere também se tenho pagamento fiscal oficialmente verificado em 2026-10 e proponha um próximo passo. Também simule o Simples usando os dados informados; não há regra revisada nesta base demonstrativa.",
                "calculation": {
                    "kind": "simples",
                    "period": "2026-10",
                    "revenue": "1000.00",
                    "rbt12": "12000.00",
                    "conditions_confirmed": True,
                },
            },
            headers={**csrf(client), "Idempotency-Key": "real-multi"},
        ).json()
        operation_id = UUID(response["operation_id"])
        with factory() as db:
            run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
            tools = AgentTools(factory, run.owner_id, run.company_id, run.context, settings)

        def legal(question):
            with factory() as db:
                return retrieve_legal(
                    db,
                    index,
                    question,
                    tools.context,
                    models.embed_question,
                    5,
                    0,
                    collection=collection,
                )

        tools.legal = legal
        from app.assistant.agents.llm import AgentModel
        from pydantic import ValidationError

        errors = []

        class DiagnosticModel(AgentModel):
            def generate(self, *args, **kwargs):
                try:
                    return super().generate(*args, **kwargs)
                except ValidationError as error:
                    errors.append(
                        (args[0], [(item["loc"], item["type"]) for item in error.errors()])
                    )
                    raise
                except ValueError as error:
                    errors.append((args[0], str(error)))
                    raise

        import subprocess
        import sys
        from pathlib import Path

        import app.assistant.agents.executor as runtime

        render = runtime.render_answer

        def terminate_after_checkpoint(*args):
            raise SystemExit("simulated worker termination after synthesis")

        monkeypatch.setattr(runtime, "render_answer", terminate_after_checkpoint)
        with pytest.raises(SystemExit):
            execute_run(
                factory,
                operation_id,
                settings=settings,
                tools=tools,
                model=DiagnosticModel(settings),
            )
        monkeypatch.setattr(runtime, "render_answer", render)
        environment = {
            **os.environ,
            "DATABASE_URL": settings.database_url,
            "REDIS_URL": settings.redis_url,
            "OLLAMA_URL": str(settings.ollama_url),
            "QDRANT_URL": str(settings.qdrant_url),
            "PYTHONPATH": str(Path("backend/api").resolve()),
        }
        command = [
            sys.executable,
            "-c",
            "import sys; from app.jobs.worker import run_operation; run_operation(sys.argv[1])",
            str(operation_id),
        ]
        for _ in range(2):
            process = subprocess.run(
                command, env=environment, capture_output=True, text=True, timeout=30
            )
            assert process.returncode == 0, process.stderr[-2000:]

        status = client.get(response["status_url"]).json()
        with factory() as db:
            run = db.scalar(select(AgentRun).where(AgentRun.operation_id == operation_id))
            steps = db.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all()
            diagnostic = [(s.name, s.status, s.error) for s in steps]
        print("REAL_AGENT_RESULTS", [(s.name, s.result) for s in steps])
        assert status["status"] == "succeeded", (status, diagnostic, errors)
        assert {"plan", "legal", "fiscal", "planning", "synthesis"} <= {s.name for s in steps}, (
            diagnostic
        )
        answer = client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"][-1]
        assert answer["citations"], [(s.name, s.result) for s in steps]
        assert "não verificada" in answer["text"]
        assert "Não há regra revisada" in answer["text"]
        assert len(answer["actions"]) <= 3
        assert len(client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"]) == 2
        print("REAL_AGENT_USAGE", [(s.name, s.usage) for s in steps])
    finally:
        if index.collection_exists(collection):
            index.delete_collection(collection)
        index.close()
        models.close()
