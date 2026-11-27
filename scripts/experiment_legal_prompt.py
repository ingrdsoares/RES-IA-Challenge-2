"""Controlled prompt ablation; reads saved evidence, never changes product code or data."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/api"))

import ollama
from app.assistant.agents.contracts import LegalResult
from app.assistant.agents.llm import transport_schema
from app.config import Settings
from app.llm_client import chat
from app.prompt_management import load_prompt


def main():
    prompt = load_prompt("evaluation/legal-ablation")
    source = ROOT / "docs/avaliacao/2026-11-17-bateria-50-agentes.json"
    output = ROOT / "docs/avaliacao/2026-11-17-experimento-prompt-juridico.json"
    baseline = json.loads(source.read_text())
    data = (
        json.loads(output.read_text())
        if output.exists()
        else {
            "experiment": "A/B do prompt jurídico, sem mudar modelo, pergunta, evidência, schema ou parâmetros de geração",
            "baseline_revision": baseline["metadata"]["revision"],
            "baseline_prompt_version": "multiagent-v2",
            "experimental_prompt": prompt.text,
            "experimental_prompt_version": prompt.version,
            "cases": [],
        }
    )
    if data.get("experimental_prompt") != prompt.text:
        raise ValueError("O prompt publicado não corresponde ao experimento salvo.")
    done = {c["id"] for c in data["cases"]}
    settings = Settings()
    client = ollama.Client(host=str(settings.ollama_url), timeout=settings.agent_timeout)
    try:
        for case in baseline["cases"]:
            legal = next(
                (
                    s
                    for s in case["agents"]
                    if s["name"] == "legal"
                    and s["status"] == "succeeded"
                    and s.get("result", {}).get("claims")
                ),
                None,
            )
            if not legal or case["id"] in done:
                continue
            print("START", case["id"], flush=True)
            entry = {
                "id": case["id"],
                "question": case["question"],
                "expected": case["expected"],
                "baseline_legal_result": legal["result"],
                "baseline_usage": legal["usage"],
                "input": legal["tool_result"],
            }
            started = time.monotonic()
            try:
                response = chat(
                    settings.model_copy(update={"llm_provider": "ollama"}),
                    [
                        {"role": "system", "content": prompt.text},
                        {
                            "role": "user",
                            "content": json.dumps(legal["tool_result"], ensure_ascii=False),
                        },
                    ],
                    prompt=prompt,
                    schema=transport_schema(LegalResult.model_json_schema()),
                    think=False,
                    max_tokens=settings.num_predict,
                    ollama_client=client,
                )
                result = LegalResult.model_validate_json(response.texto)
                allowed = set(legal["tool_result"]["sources"])
                assert all(set(claim.support_ids) <= allowed for claim in result.claims), (
                    "ID não retornado pelas fontes"
                )
                entry["experimental_result"] = result.model_dump(mode="json")
                entry["usage"] = {
                    "input_tokens": response.tokens_in,
                    "output_tokens": response.tokens_out,
                }
            except Exception as error:
                entry["error"] = {"type": type(error).__name__, "message": str(error)[:1000]}
            entry["seconds"] = round(time.monotonic() - started, 3)
            data["cases"].append(entry)
            output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            print(
                "DONE",
                case["id"],
                entry.get("experimental_result", {}).get("status", entry.get("error")),
                flush=True,
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()
