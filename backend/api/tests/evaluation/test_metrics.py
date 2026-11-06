from evaluation.metrics.bert import BertMetric
from evaluation.schemas import MetricConfig


class Tokenizer:
    model_max_length = 8

    def encode(self, text, add_special_tokens=True, truncation=False):
        return list(range(len(text.split()) + 2))

    def decode(self, tokens, skip_special_tokens=True):
        return " ".join("word" for _ in tokens)


class Scorer:
    _tokenizer = Tokenizer()
    hash = "controlled-test"
    calls = 0

    def score(self, cands, refs, batch_size):
        self.calls += 1
        if "bad" in cands:
            raise ValueError("invalid fixture")
        return [[0.9] * len(cands), [0.8] * len(cands), [0.85] * len(cands)]


def test_batches_and_partial_failures():
    scorer = Scorer()
    metric = BertMetric(
        MetricConfig(), ["reference"], scorer=scorer, prepared={"revision": "test-only"}
    )
    scores = metric.score_pairs(
        [("reference", "good"), ("reference", "bad"), ("reference", " ".join(["long"] * 10))]
    )
    assert [s.state for s in scores] == ["success", "error", "error"]
    assert scores[0].f1 == 0.85
    assert scores[2].error == "text_exceeds_model_limit"
