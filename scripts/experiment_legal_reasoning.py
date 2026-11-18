"""Diagnostic probe on incorrect published cases, with no runtime changes.

Unlike the prompt-only ablation, this condition changes thinking and output budget.
No model reasoning text is persisted: only the validated answer and token metrics.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/api"))

import ollama
from app.assistant.agents.contracts import LegalResult
from app.assistant.agents.llm import transport_schema
from app.assistant.agents.prompts import PROMPTS
from app.config import Settings


def main():
    raw = json.loads((ROOT / "docs/avaliacao/2026-11-17-bateria-50-agentes.json").read_text())
    output = ROOT / "docs/avaliacao/2026-11-17-experimento-raciocinio-juridico.json"
    results = {
        "condition": "Original legal prompt, exact original evidence and question; think=True; num_predict=4096 instead of 1024. Two settings change together; this is not a pure thinking ablation.",
        "cases": [],
    }
    settings = Settings()
    client = ollama.Client(host=str(settings.ollama_url), timeout=180)
    try:
        for case in raw["cases"]:
            if case["evaluation"]["classification"] != "incorreta":
                continue
            original = next(a for a in case["agents"] if a["name"] == "legal")
            record = {
                "id": case["id"],
                "question": case["question"],
                "baseline_result": original["result"],
            }
            print("START", case["id"], flush=True)
            started = time.monotonic()
            try:
                response = client.chat(
                    model=settings.generation_model,
                    messages=[
                        {"role": "system", "content": PROMPTS["legal"]},
                        {
                            "role": "user",
                            "content": json.dumps(original["tool_result"], ensure_ascii=False),
                        },
                    ],
                    format=transport_schema(LegalResult.model_json_schema()),
                    stream=False,
                    think=True,
                    options={
                        "temperature": 0,
                        "seed": 42,
                        "num_ctx": settings.num_ctx,
                        "num_predict": 4096,
                    },
                )
                record["result"] = LegalResult.model_validate_json(
                    response.message.content
                ).model_dump(mode="json")
                record["usage"] = {
                    "input_tokens": response.prompt_eval_count,
                    "output_tokens": response.eval_count,
                }
            except Exception as error:
                record["error"] = {"type": type(error).__name__, "message": str(error)[:1000]}
            record["seconds"] = round(time.monotonic() - started, 3)
            results["cases"].append(record)
            output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
            print("DONE", case["id"], flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
