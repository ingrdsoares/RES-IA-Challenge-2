import hashlib
import json
import random
import unicodedata
from collections import Counter
from pathlib import Path

from evaluation.schemas import DatasetSelection, EvalCase, SelectionConfig


def canonical_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_dataset(path: Path) -> list[EvalCase]:
    text = path.read_text(encoding="utf-8")
    raw = (
        [json.loads(line) for line in text.splitlines() if line.strip()]
        if path.suffix == ".jsonl"
        else json.loads(text)
    )
    if not isinstance(raw, list) or not raw:
        raise ValueError("Dataset deve conter uma lista não vazia de casos")
    cases = [EvalCase.model_validate(item) for item in raw]
    ids, questions, groups = set(), set(), {}
    for case in cases:
        question = " ".join(unicodedata.normalize("NFKC", case.question).casefold().split())
        if case.id in ids or question in questions:
            raise ValueError("ID ou pergunta duplicados")
        if case.equivalent_sources and not case.expected_sources:
            raise ValueError("equivalent_sources exige expected_sources")
        ids.add(case.id)
        questions.add(question)
        if case.group_id:
            if case.group_id in groups and groups[case.group_id] != case.split:
                raise ValueError("Grupo compartilhado entre development e final")
            groups[case.group_id] = case.split
    return cases


def select_cases(cases: list[EvalCase], config: SelectionConfig) -> DatasetSelection:
    ordered = sorted(cases, key=lambda c: c.id)
    eligible = [c for c in ordered if c.split == config.split]
    if not eligible:
        raise ValueError("Nenhuma pergunta disponível no split")
    mode = config.preset or ("custom" if config.limit else "all" if config.all_cases else "pilot")
    limit = config.limit or (
        30 if mode == "pilot" else 200 if mode == "reference" else len(eligible)
    )
    if mode == "pilot" and len(eligible) < 30:
        raise ValueError("Piloto exige 30 perguntas únicas; use limite explícito para exploração")
    if config.limit and limit > len(eligible):
        raise ValueError("Limite excede perguntas disponíveis")
    chosen = random.Random(config.seed).sample(eligible, min(limit, len(eligible)))
    return DatasetSelection(
        cases=chosen,
        dataset_hash=canonical_hash([c.model_dump() for c in ordered]),
        selection_hash=canonical_hash([c.model_dump() for c in chosen]),
        distribution=dict(Counter(c.category for c in chosen)),
        available=dict(Counter(c.expected_behavior for c in eligible)),
        available_by_category={
            category: dict(Counter(c.expected_behavior for c in eligible if c.category == category))
            for category in {c.category for c in eligible}
        },
    )
