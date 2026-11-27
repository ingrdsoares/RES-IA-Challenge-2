"""Run real agent conversations against the populated local application.

Uses synthetic company profiles, the existing legal index and real Ollama inference.
Does not recreate tables, publish fiscal rules or change model prompts. Each case is
persisted immediately so an interrupted evaluation can be inspected and resumed.
"""

import argparse
import hashlib
import json
import logging
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import ollama

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/api"))

from app.assistant.agents.executor import execute_run
from app.assistant.agents.llm import AgentModel
from app.assistant.agents.models import AgentRun, AgentStep
from app.assistant.agents.tools import AgentTools
from app.config import Settings
from app.db import session_factory
from app.legal.hybrid import active_collection
from app.legal.models import NormVersion
from app.main import create_app
from app.models import LocalModels
from app.prompt_management import prompt_scope
from app.reranker import Reranker
from app.tasks.models import Task
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import func, select


class EvaluationClient:
    """Override thinking only for this experiment; never persist reasoning text."""

    def __init__(self, client, thinking):
        self.client = client
        self.thinking = thinking

    def chat(self, **kwargs):
        return self.client.chat(**{**kwargs, "think": self.thinking})


class VerifiedRerankerClient:
    """Keep the backend reranker algorithm, but reject silent fallback in evaluations."""

    def __init__(self, client, audits):
        self.client, self.audits = client, audits

    def post(self, url, *, json):
        try:
            response = self.client.post(url, json=json)
            response.raise_for_status()
            scores = response.json()["scores"]
            if len(scores) != len(json["texts"]) or not all(
                math.isfinite(float(score)) for score in scores
            ):
                raise ValueError("Invalid scores")
        except Exception as error:
            self.audits.append({"status": "failed", "texts": len(json["texts"])})
            raise RuntimeError("Evaluation reranker failed; silent fallback rejected") from error
        self.audits.append({"status": "succeeded", "texts": len(scores)})
        return response

    def close(self):
        self.client.close()


def evaluation_parameters(settings, dataset_bytes, thinking=False):
    from app.assistant.agents.prompts import AGENT_ROLES, agent_prompt

    return {
        "model": settings.generation_model,
        "embedding_model": settings.embedding_model,
        "num_ctx": settings.num_ctx,
        "num_predict": settings.num_predict,
        "thinking": thinking,
        "max_context_chars": settings.max_context_chars,
        "agent_token_budget": settings.agent_token_budget,
        "agent_timeout": settings.agent_timeout,
        "agent_round_seconds": settings.agent_round_seconds,
        "agent_step_attempts": settings.agent_step_attempts,
        "prompt_versions": {role: agent_prompt(role).version for role in AGENT_ROLES},
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "score_threshold": settings.score_threshold,
        "top_k": settings.top_k,
        "retrieval_mode": "backend_hybrid_reranker",
        "reranker_url": str(settings.reranker_url) if settings.reranker_url else None,
        "reranker_timeout": settings.reranker_timeout,
        "ignore_validity_for_test": True,
    }


def validate_resume(result, parameters):
    if result.get("cases") and result.get("metadata", {}).get("parameters") != parameters:
        raise ValueError(
            "Parâmetros ou dataset diferentes: use outro --output para preservar a comparação"
        )


TERMINAL_STATUSES = {"succeeded", "failed", "awaiting_data"}


def completed_ids(result):
    return {
        case["id"]
        for case in result["cases"]
        if case.get("operation", {}).get("status") in TERMINAL_STATUSES
    }


def record_case(result, entry):
    for position, previous in enumerate(result["cases"]):
        if previous["id"] == entry["id"]:
            result["metadata"].setdefault("prior_nonterminal_records", []).append(previous)
            result["cases"][position] = entry
            return
    result["cases"].append(entry)


def execute_until_terminal(execute, get_status, max_attempts):
    for _ in range(max_attempts):
        execute()
        operation = get_status()
        if operation["status"] in TERMINAL_STATUSES:
            break
    return operation


@prompt_scope()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "backend/evaluation/data/agent_flow_50.json"
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--num-ctx", type=int, choices=range(8192, 40961), metavar="8192..40960")
    parser.add_argument("--num-predict", type=int, choices=range(64, 8193), metavar="64..8192")
    parser.add_argument("--reranker-url")
    args = parser.parse_args()
    settings = Settings(cookie_secure=False, allowed_origins=["http://testserver"])
    if args.reranker_url:
        settings = Settings(**{**settings.model_dump(), "reranker_url": args.reranker_url})
    if args.num_ctx is not None:
        settings = settings.model_copy(
            update={"num_ctx": args.num_ctx, "max_context_chars": args.num_ctx}
        )
    # Experimental output allowance can exceed the production setting's 1K cap.
    settings = settings.model_copy(
        update={
            "num_predict": args.num_predict or (4096 if args.thinking else settings.num_predict),
            "agent_timeout": 300 if args.thinking else settings.agent_timeout,
        }
    )
    if settings.num_predict >= settings.num_ctx - 2048:
        parser.error("Reserve at least 2048 context tokens beyond the generation allowance")
    if args.output is None:
        suffix = "-thinking" if args.thinking else ""
        args.output = (
            ROOT / "docs/avaliacao" / f"bateria-50-agentes-{settings.num_ctx}{suffix}.json"
        )
    cases = json.loads(args.dataset.read_text())
    result = (
        json.loads(args.output.read_text())
        if args.output.exists()
        else {"metadata": {}, "cases": []}
    )
    completed = completed_ids(result)
    parameters = evaluation_parameters(settings, args.dataset.read_bytes(), thinking=args.thinking)
    factory = session_factory(settings.database_url)
    index = QdrantClient(url=str(settings.qdrant_url), timeout=settings.qdrant_timeout)
    with factory() as db:
        hybrid_collection = active_collection(db)
    if not hybrid_collection or not index.collection_exists(hybrid_collection):
        raise RuntimeError("An active hybrid index is required for this evaluation")
    if not settings.reranker_url:
        raise RuntimeError("A configured reranker is required for this evaluation")
    parameters["hybrid_collection"] = hybrid_collection
    validate_resume(result, parameters)
    with httpx.Client(timeout=settings.reranker_timeout) as health:
        health.get(str(settings.reranker_url).rstrip("/") + "/health").raise_for_status()
    models = LocalModels(settings)
    generation_client = ollama.Client(host=str(settings.ollama_url), timeout=settings.agent_timeout)
    agent_model = AgentModel(settings, EvaluationClient(generation_client, args.thinking))
    with factory() as db:
        catalog = dict(
            db.execute(select(NormVersion.status, func.count()).group_by(NormVersion.status)).all()
        )
    result["metadata"].update(
        {
            "parameters": parameters,
            "revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "model": settings.generation_model,
            "embedding_model": settings.embedding_model,
            "catalog": catalog,
            "collection": hybrid_collection,
            "indexed_chunks": index.count(hybrid_collection, exact=True).count,
            "ignore_validity_for_test": True,
            "score_threshold": settings.score_threshold,
            "top_k": settings.top_k,
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

                    backend_legal = tools.legal
                    entry["retrieval_audit"] = []

                    def legal(question):
                        audit = []
                        retrieval_record = {"reranker": audit, "sources": []}
                        entry["retrieval_audit"].append(retrieval_record)
                        reranker = Reranker(
                            settings,
                            client=VerifiedRerankerClient(
                                httpx.Client(timeout=settings.reranker_timeout), audit
                            ),
                        )
                        passages = backend_legal(
                            question, ignore_validity_for_test=True, reranker=reranker
                        )
                        retrieval_record["sources"] = [
                            {"anchor_id": p["anchor_id"], "strategy": p["retrieval_strategy"]}
                            for p in passages
                        ]
                        if any(p["retrieval_strategy"] != "hybrid" for p in passages):
                            raise RuntimeError("Dense fallback rejected in evaluation")
                        return passages

                    tools.legal = legal
                    entry["operation"] = execute_until_terminal(
                        lambda: execute_run(
                            factory,
                            run.operation_id,
                            settings=settings,
                            tools=tools,
                            model=agent_model,
                        ),
                        lambda: client.get(receipt["status_url"]).json(),
                        settings.agent_step_attempts + 1,
                    )
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
                record_case(result, entry)
                save()
                if entry.get("operation", {}).get("status") in {"queued", "running"}:
                    raise RuntimeError(
                        "Nonterminal case saved; stop instead of skipping queued cases"
                    )
                print(
                    "DONE",
                    case["id"],
                    entry.get("operation", {}).get("status", entry.get("execution_error")),
                    entry["duration_seconds"],
                    flush=True,
                )
    finally:
        result["metadata"]["evaluation_status"] = (
            "complete"
            if len(result["cases"]) == len(cases)
            and all(
                c.get("operation", {}).get("status") in {"succeeded", "failed", "awaiting_data"}
                for c in result["cases"]
            )
            else "incomplete"
        )
        result["metadata"]["finished_at"] = datetime.now(UTC).isoformat()
        save()
        index.close()
        models.close()
        generation_client.close()
        factory.kw["bind"].dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
