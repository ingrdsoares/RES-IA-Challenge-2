import hashlib
import math
import unicodedata
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from evaluation.schemas import MetricScore


def package_versions():
    result = {}
    for package in ["bert-score", "transformers", "torch", "rouge-score", "numpy"]:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not_installed"
    return result


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare_model(config, allow_download=False):
    if config.bert_model_path:
        path = Path(config.bert_model_path).resolve()
        if not path.is_dir():
            raise ValueError("Diretório de modelo local ausente")
        files = sorted(p for p in path.rglob("*") if p.is_file())
        digest = hashlib.sha256()
        for p in files:
            digest.update(str(p.relative_to(path)).encode())
            digest.update(file_hash(p).encode())
        revision = digest.hexdigest()
    else:
        from huggingface_hub import snapshot_download

        path = Path(
            snapshot_download(
                repo_id=config.bert_model,
                revision=config.bert_revision or "main",
                local_files_only=not allow_download,
                allow_patterns=["*.json", "*.txt", "*.safetensors", "pytorch_model.bin", "*.model"],
            )
        )
        revision = path.name
    return {"model": config.bert_model, "path": str(path), "revision": revision, "resolved": True}


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


class BertMetric:
    def __init__(self, config, references, scorer=None, prepared=None):
        self.config = config
        self.prepared = prepared or prepare_model(config, config.allow_download)
        if config.rescale and not config.baseline_path:
            raise ValueError("Rescaling exige baseline explícito compatível com o modelo e idioma")
        if scorer is None:
            from bert_score import BERTScorer

            scorer = BERTScorer(
                model_type=self.prepared["path"],
                num_layers=config.bert_layers,
                batch_size=config.bert_batch_size,
                device=config.device,
                lang=config.lang,
                idf=config.idf,
                idf_sents=[normalize(r) for r in references] if config.idf else None,
                rescale_with_baseline=config.rescale,
                baseline_path=config.baseline_path,
                use_fast_tokenizer=False,
            )
        self.scorer = scorer
        self.tokenizer = scorer._tokenizer

    def metadata(self):
        data = self.prepared | {
            "native_hash": self.scorer.hash,
            "versions": package_versions(),
            "config": self.config.model_dump(
                exclude={"allow_download", "bert_model_path", "baseline_path"}
            ),
            "normalization": "NFC_whitespace_cased",
            "rouge_tokenizer": "NFC_casefold_unicode_alphanumeric_no_stemming",
        }
        if self.config.baseline_path:
            data["baseline_hash"] = file_hash(self.config.baseline_path)
        return data

    def score_pairs(self, pairs):
        results = [None] * len(pairs)
        valid = []
        for i, (ref, cand) in enumerate(pairs):
            texts = [normalize(ref), normalize(cand)]
            lengths = [
                len(self.tokenizer.encode(t, add_special_tokens=True, truncation=False))
                for t in texts
            ]
            limit = min(
                self.tokenizer.model_max_length,
                512
                if self.tokenizer.model_max_length > 100000
                else self.tokenizer.model_max_length,
            )
            detail = {
                "original_tokens": lengths,
                "token_limit": limit,
                "truncated": max(lengths) > limit,
            }
            if detail["truncated"] and self.config.overflow == "error":
                results[i] = MetricScore(
                    state="error", error="text_exceeds_model_limit", details=detail
                )
                continue
            if detail["truncated"]:
                texts = [
                    self.tokenizer.decode(
                        self.tokenizer.encode(t, add_special_tokens=False, truncation=False)[
                            : limit - 2
                        ],
                        skip_special_tokens=True,
                    )
                    for t in texts
                ]
                detail["evaluated_tokens"] = [
                    len(self.tokenizer.encode(t, add_special_tokens=True, truncation=False))
                    for t in texts
                ]
            valid.append((i, texts[0], texts[1], detail))

        def batch(rows):
            if not rows:
                return
            try:
                p, r, f = self.scorer.score(
                    [x[2] for x in rows],
                    [x[1] for x in rows],
                    batch_size=self.config.bert_batch_size,
                )
                for row, pv, rv, fv in zip(rows, p, r, f, strict=True):
                    values = [float(pv), float(rv), float(fv)]
                    if not all(math.isfinite(v) for v in values):
                        results[row[0]] = MetricScore(state="error", error="nonfinite_score")
                    else:
                        results[row[0]] = MetricScore(
                            state="success",
                            precision=values[0],
                            recall=values[1],
                            f1=values[2],
                            details=row[3],
                        )
            except Exception as exc:
                if len(rows) == 1:
                    results[rows[0][0]] = MetricScore(state="error", error=type(exc).__name__)
                else:
                    midpoint = len(rows) // 2
                    batch(rows[:midpoint])
                    batch(rows[midpoint:])

        for offset in range(0, len(valid), self.config.bert_batch_size):
            batch(valid[offset : offset + self.config.bert_batch_size])
        return results
