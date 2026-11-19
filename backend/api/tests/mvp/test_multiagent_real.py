"""Opt-in real Qwen + Qdrant execution using only demonstration documents."""

import os
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_access import csrf
from test_conversations import conversation


@pytest.mark.integration
@pytest.mark.parametrize(
    "scenario", ["juridico", "fiscal", "calculo_sem_regra", "combinado", "calculo_fixture"]
)
def test_multiagent_real_qwen(client, monkeypatch, scenario):
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
                "Art. 18-A O Microempreendedor Individual pode optar pelo recolhimento em valores fixos mensais dos tributos abrangidos pelo Simples Nacional, independentemente da receita bruta do mês. Este recorte é exclusivo do teste e não comprova pagamento.".encode(),
                "text/markdown",
            )
            version = NormVersion(
                document_id=norm.id,
                version_label="demo",
                title="Recorte de teste: recolhimento mensal do MEI",
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
        questions = {
            "juridico": "Segundo o recorte fornecido do art. 18-A, o recolhimento do MEI pode ser fixo mensal independentemente da receita do mês? Explique com a fonte.",
            "fiscal": "Tenho pagamento fiscal oficialmente verificado na competência 2026-10? Consulte as evidências da minha empresa.",
            "calculo_sem_regra": "Simule o Simples Nacional da competência 2026-10 usando os dados estruturados informados. Se não existir regra revisada, informe sem inventar valor.",
            "combinado": "Explique com fonte o recolhimento mensal do MEI segundo o art. 18-A fornecido, consulte se tenho pagamento oficialmente verificado em 2026-10 e proponha um próximo passo sustentado nas conclusões.",
            "calculo_fixture": "Execute a simulação demonstrativa do Simples em 2026-10 com os dados estruturados fornecidos. Explique o resultado do motor, sem afirmar pagamento.",
        }
        request = {"text": questions[scenario]}
        if scenario in ("calculo_sem_regra", "calculo_fixture"):
            request["calculation"] = {
                "kind": "simples",
                "period": "2026-10",
                "revenue": "10000.00",
                "rbt12": "500000.00",
                "payroll12": "140000.00",
                "conditions_confirmed": True,
            }
        if scenario == "calculo_fixture":
            from app.fiscal.registry import import_rule, review_rule
            from app.fiscal.schemas import RuleInput
            from test_fiscal_calculations import SIMPLES

            with factory.begin() as db:
                rule = import_rule(
                    db,
                    RuleInput(
                        kind="simples",
                        version="synthetic-test-only",
                        valid_from="2026-10",
                        valid_to="2026-10",
                        parameters=SIMPLES,
                        references=["https://example.org/synthetic-fixture"],
                    ),
                )
                review_rule(
                    db,
                    rule.id,
                    "synthetic-test-only",
                    "Parâmetros artificiais exclusivos de teste, sem validade tributária",
                )
        response = client.post(
            "/conversas/" + chat["id"] + "/mensagens",
            json=request,
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
        expected = {"plan", "synthesis"}
        if scenario in ("juridico", "combinado"):
            expected.add("legal")
        if scenario != "juridico":
            expected.add("fiscal")
        if scenario == "combinado":
            expected.add("planning")
        assert expected == {step.name for step in steps}, diagnostic
        answer = client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"][-1]
        if scenario in ("juridico", "combinado"):
            assert "fix" in answer["text"].lower() and "mens" in answer["text"].lower()
            assert "biblioteca" not in answer["text"].lower()
            assert answer["citations"], [(step.name, step.result) for step in steps]
        if scenario != "juridico":
            assert "não verificada" in answer["text"]
        if scenario == "calculo_sem_regra":
            assert "Não há regra revisada" in answer["text"]
        if scenario == "calculo_fixture":
            assert "800.00" in answer["text"], answer
        if scenario == "combinado":
            assert 1 <= len(answer["actions"]) <= 3
        assert len(client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"]) == 2
        import json

        artifact = Path(
            os.getenv("AGENT_PRACTICAL_REPORT_DIR", "/private/tmp/res-ia-agent-practical")
        )
        artifact.mkdir(parents=True, exist_ok=True)
        (artifact / (scenario + ".json")).write_text(
            json.dumps(
                {
                    "scenario": scenario,
                    "question": request,
                    "answer": answer,
                    "agents": [
                        {"role": step.name, "result": step.result, "usage": step.usage}
                        for step in steps
                    ],
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        print("REAL_AGENT_USAGE", [(s.name, s.usage) for s in steps])
    finally:
        if index.collection_exists(collection):
            index.delete_collection(collection)
        index.close()
        models.close()
