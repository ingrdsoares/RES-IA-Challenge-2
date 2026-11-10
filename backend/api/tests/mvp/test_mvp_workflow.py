"""Opt-in workflow against an isolated running Compose project, never production."""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.integration


def wait_for(check, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.3)
    pytest.fail("Workflow did not complete before timeout")


def test_mvp_workflow(tmp_path):
    base = os.getenv("MVP_TEST_URL")
    if not base:
        pytest.skip("requires MVP_TEST_URL and isolated MVP_DATABASE_URL / MVP_S3_URL")
    from app.config import Settings
    from app.db import session_factory
    from app.legal.ingest import ingest_file, storage_from_settings
    from app.legal.schemas import IngestMetadata

    settings = Settings(
        database_url=os.environ["MVP_DATABASE_URL"],
        s3_endpoint=os.environ["MVP_S3_URL"],
        s3_public_endpoint=os.environ["MVP_S3_URL"],
        allowed_origins=[base],
    )
    factory = session_factory(settings.database_url)
    with httpx.Client(base_url=base, timeout=30) as client:

        def headers(key=None):
            token = client.get("/auth/csrf").json()["csrf_token"]
            return {
                "Origin": base,
                "X-CSRF-Token": token,
                **({"Idempotency-Key": key} if key else {}),
            }

        assert client.get("/health").status_code == 200
        registration = client.post(
            "/auth/register",
            json={"email": uuid4().hex + "@example.org", "password": "workflow long password"},
            headers=headers(),
        )
        assert registration.status_code == 201, registration.text
        company = client.post(
            "/empresas",
            json={
                "cnpj": "11222333000181",
                "cnae": "6201501",
                "size": "ME",
                "regime": "simples",
                "municipality": "Brasília",
                "state": "DF",
            },
            headers=headers(),
        ).json()
        path = tmp_path / "demo.md"
        path.write_text(
            "Art. 1 A biblioteca demonstrativa organiza documentos por assunto e permite consultar a versão citada na conversa."
        )
        metadata = IngestMetadata(
            document_key="workflow-" + uuid4().hex,
            title="Norma demonstrativa",
            authority="Teste",
            jurisdiction="BR",
            norm_type="demonstracao",
            version_label="v1",
            official_url="https://example.org/workflow",
            effective_from="2020-01-01",
        )
        with factory.begin() as db:
            version_id = ingest_file(
                path,
                metadata,
                "workflow-" + uuid4().hex,
                db=db,
                storage=storage_from_settings(settings),
            )
        wait_for(
            lambda: any(
                row["version_id"] == str(version_id)
                for row in client.get("/normas", params={"q": metadata.document_key}).json()[
                    "items"
                ]
            )
        )
        chat = client.post(
            "/empresas/" + company["id"] + "/conversas", json={}, headers=headers()
        ).json()
        url = "/conversas/" + chat["id"] + "/mensagens"
        key = uuid4().hex
        sent = client.post(
            url,
            json={"text": "Como a biblioteca demonstrativa organiza documentos?"},
            headers=headers(key),
        ).json()

        def result():
            response = client.get(sent["status_url"]).json()
            if response["status"] == "failed":
                pytest.fail(str(response))
            return response if response["status"] == "succeeded" else None

        wait_for(result)
        messages = client.get(url).json()["items"]
        assert len(messages) == 2
        assert messages[-1]["status"] == "answered", messages[-1]
        citation = messages[-1]["citations"][0]
        reader = client.get(
            "/citacoes/resolver",
            params={key: citation[key] for key in ("document_id", "version_id", "anchor_id")},
        ).json()
        assert reader["state"] == "exact"
        assert httpx.get(reader["json_url"]).status_code == 200
        assert (
            client.post(
                url,
                json={"text": "Como a biblioteca demonstrativa organiza documentos?"},
                headers=headers(key),
            ).json()["operation_id"]
            == sent["operation_id"]
        )
        assert len(client.get(url).json()["items"]) == 2
        evidence = client.post(
            "/empresas/" + company["id"] + "/evidencias",
            json={"kind": "guide", "scope": "obligations", "period": "2026-10"},
            headers=headers(uuid4().hex),
        ).json()
        body = b"%PDF-1.4 synthetic document"
        assert (
            client.put(
                "/evidencias/" + evidence["id"] + "/arquivo",
                content=body,
                headers={**headers(), "Content-Type": "application/pdf"},
            ).status_code
            == 200
        )
        download = client.get("/evidencias/" + evidence["id"] + "/arquivo").json()["url"]
        assert httpx.get(download).content == body
        task = client.post(
            "/empresas/" + company["id"] + "/tarefas",
            json={"title": "Conferir guia"},
            headers=headers(),
        ).json()
        assert (
            client.patch(
                "/tarefas/" + task["id"], json={"completed": True}, headers=headers(uuid4().hex)
            ).status_code
            == 200
        )
        assert (
            client.get("/empresas/" + company["id"] + "/situacao-fiscal").json()["obligations"][
                "verification"
            ]
            == "unverified"
        )
        calculation = client.post(
            "/empresas/" + company["id"] + "/calculos",
            json={"kind": "mei", "period": "2026-10"},
            headers=headers(),
        ).json()
        assert calculation["status"] == "rule_unavailable"
        if os.getenv("MVP_RESULT_FILE"):
            Path(os.environ["MVP_RESULT_FILE"]).write_text(
                json.dumps({"conversation_id": chat["id"], "operation_id": sent["operation_id"]})
            )
    factory.kw["bind"].dispose()
