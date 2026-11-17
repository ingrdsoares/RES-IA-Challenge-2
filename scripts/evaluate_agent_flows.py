"""Run real agent conversations against the populated local application.

Uses synthetic company profiles, the existing legal index and real Ollama inference.
Does not recreate tables, publish fiscal rules or change model prompts. Each case is
persisted immediately so an interrupted evaluation can be inspected and resumed.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/api"))

from app.assistant.agents.executor import execute_run
from app.assistant.agents.models import AgentRun, AgentStep
from app.assistant.agents.tools import AgentTools
from app.assistant.tools import retrieve_legal
from app.config import Settings
from app.db import session_factory
from app.legal.index import COLLECTION
from app.legal.models import NormVersion
from app.main import create_app
from app.models import LocalModels
from app.tasks.models import Task
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import func, select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "backend/evaluation/data/agent_flow_50.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/avaliacao/2026-11-17-bateria-50-agentes.json"
    )
    args = parser.parse_args()
    cases = json.loads(args.dataset.read_text())
    result = (
        json.loads(args.output.read_text())
        if args.output.exists()
        else {"metadata": {}, "cases": []}
    )
    completed = {case["id"] for case in result["cases"]}
    settings = Settings(cookie_secure=False, allowed_origins=["http://testserver"])
    factory = session_factory(settings.database_url)
    index = QdrantClient(url=str(settings.qdrant_url), timeout=settings.qdrant_timeout)
    models = LocalModels(settings)
    with factory() as db:
        catalog = dict(
            db.execute(select(NormVersion.status, func.count()).group_by(NormVersion.status)).all()
        )
    result["metadata"].update(
        {
            "revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "model": settings.generation_model,
            "embedding_model": settings.embedding_model,
            "catalog": catalog,
            "collection": COLLECTION,
            "indexed_chunks": index.count(COLLECTION, exact=True).count,
            "ignore_validity_for_test": True,
            "score_threshold": 0.3,
            "top_k": 5,
            "synthetic_profiles": True,
            "fiscal_rules_published_by_runner": False,
            "started_at": result["metadata"].get("started_at", datetime.now(UTC).isoformat()),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
        temporary.replace(args.output)

    save()
    try:
        with TestClient(create_app(settings=settings)) as client:

            def headers(key=None):
                value = {
                    "Origin": "http://testserver",
                    "X-CSRF-Token": client.get("/auth/csrf").json()["csrf_token"],
                }
                if key:
                    value["Idempotency-Key"] = key
                return value

            register = client.post(
                "/auth/register",
                json={
                    "email": "agent-eval-" + uuid4().hex + "@example.org",
                    "password": "local evaluation account password",
                },
                headers=headers(),
            )
            register.raise_for_status()
            companies = {}
            for profile, cnpj, cnae, size in [
                ("mei", "11222333000181", "9602501", "MEI"),
                ("simples", "11444777000161", "6201501", "ME"),
            ]:
                response = client.post(
                    "/empresas",
                    json={
                        "cnpj": cnpj,
                        "cnae": cnae,
                        "size": size,
                        "regime": profile,
                        "municipality": "Brasília",
                        "state": "DF",
                    },
                    headers=headers(),
                )
                response.raise_for_status()
                companies[profile] = response.json()
            evidence = client.post(
                "/empresas/" + companies["mei"]["id"] + "/evidencias",
                json={"kind": "guide", "scope": "obligations", "period": "2026-10"},
                headers=headers(uuid4().hex),
            )
            evidence.raise_for_status()
            for case in cases:
                if case["id"] in completed:
                    continue
                started = time.monotonic()
                entry = {**case, "evaluation": "pendente de revisão qualitativa"}
                print("START", case["id"], case["question"], flush=True)
                try:
                    company = companies[case["profile"]]
                    chat = client.post(
                        "/empresas/" + company["id"] + "/conversas",
                        json={"title": case["id"] + " avaliação"},
                        headers=headers(),
                    )
                    chat.raise_for_status()
                    chat = chat.json()
                    body = {"text": case["question"]}
                    if "calculation" in case:
                        body["calculation"] = case["calculation"]
                    receipt = client.post(
                        "/conversas/" + chat["id"] + "/mensagens",
                        json=body,
                        headers=headers(uuid4().hex),
                    )
                    receipt.raise_for_status()
                    receipt = receipt.json()
                    with factory() as db:
                        run = db.scalar(
                            select(AgentRun).where(
                                AgentRun.operation_id == UUID(receipt["operation_id"])
                            )
                        )
                    tools = AgentTools(factory, run.owner_id, run.company_id, run.context, settings)

                    def legal(question, context=run.context):
                        with factory() as db:
                            return retrieve_legal(
                                db,
                                index,
                                question,
                                context,
                                models.embed_question,
                                5,
                                0.3,
                                ignore_validity_for_test=True,
                            )

                    tools.legal = legal
                    execute_run(factory, run.operation_id, settings=settings, tools=tools)
                    entry["operation"] = client.get(receipt["status_url"]).json()
                    messages = client.get("/conversas/" + chat["id"] + "/mensagens").json()["items"]
                    entry["response"] = next(
                        (item for item in reversed(messages) if item["role"] == "assistant"), None
                    )
                    with factory() as db:
                        steps = db.scalars(
                            select(AgentStep)
                            .where(AgentStep.run_id == run.id)
                            .order_by(AgentStep.created_at, AgentStep.id)
                        ).all()
                        entry["agents"] = [
                            {
                                "name": step.name,
                                "status": step.status,
                                "error": step.error,
                                "result": step.result,
                                "usage": step.usage,
                                "tool_result": step.tool_result,
                            }
                            for step in steps
                        ]
                        entry["tasks_created"] = db.scalar(
                            select(func.count())
                            .select_from(Task)
                            .where(Task.company_id == UUID(company["id"]))
                        )
                except Exception as error:
                    entry["execution_error"] = {
                        "type": type(error).__name__,
                        "message": str(error)[:1000],
                    }
                entry["duration_seconds"] = round(time.monotonic() - started, 3)
                result["cases"].append(entry)
                save()
                print(
                    "DONE",
                    case["id"],
                    entry.get("operation", {}).get("status", entry.get("execution_error")),
                    entry["duration_seconds"],
                    flush=True,
                )
    finally:
        result["metadata"]["finished_at"] = datetime.now(UTC).isoformat()
        save()
        index.close()
        models.close()
        factory.kw["bind"].dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
