import pytest
from evaluation.dataset import load_dataset, select_cases
from evaluation.schemas import SelectionConfig


def test_duplicate_questions_rejected(tmp_path):
    p = tmp_path / "cases.json"
    p.write_text(
        '[{"id":"a","category":"x","question":"AÇÃO?","ground_truth":"x"},{"id":"b","category":"x","question":"ação?","ground_truth":"x"}]'
    )
    with pytest.raises(ValueError):
        load_dataset(p)


def test_pilot_does_not_invent_cases():
    with pytest.raises(ValueError):
        select_cases([], SelectionConfig())
