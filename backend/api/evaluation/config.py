import json
import os
from pathlib import Path
from evaluation.schemas import EvalConfig


def merge(a: dict, b: dict) -> dict:
    result = dict(a)
    for key, value in b.items():
        if value is None:
            continue
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else value
    return result


def resolve_config(file: Path | None, overrides: dict) -> EvalConfig:
    env = {}
    defaults = EvalConfig().model_dump()
    for section, fields in defaults.items():
        for key in fields:
            if key == 'selection':
                continue
            value = os.getenv('EVAL_' + key.upper())
            if value is not None:
                env.setdefault(section, {})[key] = value
    config = merge(env, json.loads(file.read_text()) if file else {})
    return EvalConfig.model_validate(merge(config, overrides))
