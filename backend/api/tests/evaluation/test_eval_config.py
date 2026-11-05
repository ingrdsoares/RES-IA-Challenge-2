import json

import pytest
from evaluation.config import resolve_config
from evaluation.schemas import StatsConfig


def test_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_BOOTSTRAP", "100")
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"stats": {"bootstrap": 200}}))
    assert resolve_config(p, {"stats": {"bootstrap": 300}}).stats.bootstrap == 300
    assert resolve_config(p, {}).stats.bootstrap == 200
    assert resolve_config(None, {}).stats.bootstrap == 100


def test_margin_must_be_positive():
    with pytest.raises(ValueError):
        StatsConfig(margin=0)
