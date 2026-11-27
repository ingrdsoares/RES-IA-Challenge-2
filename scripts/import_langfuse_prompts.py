"""Publish the original templates without overwriting existing production prompts."""

import json
import sys
from pathlib import Path

from langfuse.api.resources.commons.errors.not_found_error import NotFoundError

API = Path(__file__).resolve().parents[1] / "backend" / "api"
sys.path.insert(0, str(API))

from app.prompt_management import client


def publish(sdk, name, text):
    try:
        return sdk.get_prompt(name, label="production", type="text", cache_ttl_seconds=0)
    except NotFoundError:
        try:
            existing = sdk.get_prompt(name, label="latest", type="text", cache_ttl_seconds=0)
        except NotFoundError:
            return sdk.create_prompt(name=name, prompt=text, type="text", labels=["production"])
        raise SystemExit(
            f"{name} já existe na versão {existing.version}. "
            "Escolha uma versão para o label production no Langfuse e execute novamente."
        ) from None


def main():
    sdk = client()
    if sdk is None:
        raise SystemExit("Configure LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY no ambiente.")
    catalog = json.loads((API / "prompt_catalog.json").read_text())
    for name, text in catalog.items():
        prompt = publish(sdk, name, text)
        print(f"{name} v{prompt.version}")


if __name__ == "__main__":
    main()
