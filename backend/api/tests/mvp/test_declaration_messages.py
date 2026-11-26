from pathlib import Path

from test_access import csrf
from test_conversations import conversation
from test_guide_messages import PNG, post_message, run_guide

DASN = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "benchmark"
    / "multimodal"
    / "dasn_simei_excesso_92k.pdf"
).read_bytes()


def attach(client, company, key, kind, media_type, content):
    response = client.post(
        f"/empresas/{company['id']}/evidencias",
        json={"kind": kind, "scope": "obligations"},
        headers={**csrf(client), "Idempotency-Key": key},
    )
    assert response.status_code == 201
    item = response.json()
    response = client.put(
        f"/evidencias/{item['id']}/arquivo",
        content=content,
        headers={**csrf(client), "Content-Type": media_type},
    )
    assert response.status_code == 200
    return item["id"]


class DocumentOnly:
    def generate(self, role, schema, payload, timeout, output_tokens):
        assert role == "plan"
        assert "declaration_reading" in payload["context"]
        return schema(intent="Ler declaração", agents=[]), {}


def test_declaration_pdf_is_offered_and_accepted_without_image_reading(client):
    company, chat = conversation(client)
    declaration = attach(client, company, "dasn", "declaration", "application/pdf", DASN)
    attach(client, company, "guide-png", "guide", "image/png", PNG)
    attach(client, company, "guide-pdf", "guide", "application/pdf", b"%PDF-1.4")
    url = f"/empresas/{company['id']}/guias-para-assistente"
    body = client.get(url).json()
    # Image reading is off: only the locally read declaration is offered.
    assert body["enabled"] is False
    assert [(item["id"], item["kind"], item["media_type"]) for item in body["items"]] == [
        (declaration, "declaration", "application/pdf")
    ]
    response = post_message(
        client, chat, "ask", text="Estourei o limite do MEI?", evidence_id=declaration
    )
    assert response.status_code == 202


def test_worker_reads_declaration_locally_and_answers_from_it(client, monkeypatch):
    from app.assistant.agents import executor

    def no_external_call(*args, **kwargs):
        raise AssertionError("PDF não deve ir ao provedor de visão")

    monkeypatch.setattr(executor, "read_guide", no_external_call, raising=False)
    company, chat = conversation(client)
    declaration = attach(client, company, "dasn", "declaration", "application/pdf", DASN)
    submitted = post_message(
        client, chat, "read", text="O que diz esta declaração?", evidence_id=declaration
    ).json()
    status = run_guide(client, submitted, DocumentOnly())
    assert status["status"] == "succeeded"
    assert [step["name"] for step in status["run"]["stages"]] == ["document", "plan"]
    assert status["run"]["stages"][0]["model"] == "dasn-pdf-parser"
    answer = client.get(f"/conversas/{chat['id']}/mensagens").json()["items"][-1]
    reading = answer["context"]["declaration_reading"]
    assert reading["evidence_id"] == declaration
    assert reading["receita_total"] == "92000.00"
    assert reading["excesso_valor"] == "11000.00"
    assert reading["faixa_excesso"] == "ate_20_porcento"
    assert answer["text"] == "Consulte os dados lidos na declaração."


def test_fiscal_agent_receives_declaration_as_citable_support(client):
    from test_multiagent_workflow import Model

    company, chat = conversation(client)
    declaration = attach(client, company, "dasn", "declaration", "application/pdf", DASN)
    seen = {}

    class FiscalModel(Model):
        def generate(self, role, schema, payload, timeout, output_tokens):
            if role == "plan":
                return schema(intent="limite", agents=["fiscal"]), {}
            if role == "fiscal":
                seen.update(payload)
                return schema.model_validate(
                    {
                        "status": "answered",
                        "claims": [
                            {
                                "text": "A declaração indica receita de R$ 92.000,00.",
                                "support_ids": ["evidence:" + declaration],
                            }
                        ],
                    }
                ), {}
            if role == "synthesis":
                return schema.model_validate(
                    {"answer": "Receita declarada acima do limite.", "support_ids": []}
                ), {}
            return super().generate(role, schema, payload, timeout, output_tokens)

    submitted = post_message(
        client, chat, "limit", text="Estourei o limite do MEI?", evidence_id=declaration
    ).json()
    status = run_guide(client, submitted, FiscalModel())
    assert status["status"] == "succeeded"
    support = seen["support"]["evidence:" + declaration]
    assert support["receita_total"] == "92000.00"
    assert seen["declaration"]["excesso_percentual"] == "13.58"
    answer = client.get(f"/conversas/{chat['id']}/mensagens").json()["items"][-1]["text"]
    assert "receita bruta de R$ 92.000,00, acima do limite anual de R$ 81.000,00" in answer
    assert "desenquadramento a partir de 01/01/2026" in answer


def test_unreadable_declaration_says_so_without_values(client):
    company, chat = conversation(client)
    broken = attach(client, company, "broken", "declaration", "application/pdf", b"%PDF-1.4 x")
    submitted = post_message(
        client, chat, "broken", text="O que diz esta declaração?", evidence_id=broken
    ).json()
    assert run_guide(client, submitted, DocumentOnly())["status"] == "succeeded"
    answer = client.get(f"/conversas/{chat['id']}/mensagens").json()["items"][-1]
    assert answer["context"]["declaration_reading"]["legible"] is False
    assert answer["text"] == (
        "Não consegui ler a declaração. Envie o PDF original da DASN-SIMEI gerado no portal "
        "do Simples Nacional."
    )
