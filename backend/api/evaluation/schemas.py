from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas import QueryRequest


class EvalCase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    category: str
    question: str
    ground_truth: str
    expected_sources: list[str | int] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    expected_behavior: Literal['answer', 'abstain', 'clarify'] = 'answer'
    split: Literal['development', 'final'] = 'development'
    group_id: str | None = None

    @field_validator('id', 'category', 'question', 'ground_truth')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Campo vazio')
        return value

    @field_validator('question')
    @classmethod
    def question_contract(cls, value):
        QueryRequest(question=value)
        return value


class SelectionConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preset: Literal['pilot', 'reference'] | None = None
    limit: int | None = Field(default=None, gt=0)
    all_cases: bool = False
    split: Literal['development', 'final'] = 'development'
    seed: int = 42

    @model_validator(mode='after')
    def exclusive(self):
        if sum([self.preset is not None, self.limit is not None, self.all_cases]) > 1:
            raise ValueError('Escolha preset, limite ou todos')
        if self.split == 'final' and self.limit is None and not self.all_cases and self.preset != 'reference':
            raise ValueError('Piloto não pode usar conjunto final')
        return self


class DatasetSelection(BaseModel):
    cases: list[EvalCase]
    dataset_hash: str
    selection_hash: str
    distribution: dict[str, int]
    available: dict[str, int]
    available_by_category: dict[str, dict[str, int]] = Field(default_factory=dict)


class RunConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    repeats: int = Field(default=1, ge=1)
    rag_version: str = ''
    corpus_version: str = ''


class MetricConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bert_model: str = 'neuralmind/bert-base-portuguese-cased'
    bert_revision: str | None = None
    bert_model_path: str | None = None
    bert_layers: int = Field(default=12, ge=1)
    bert_batch_size: int = Field(default=4, ge=1)
    device: str = 'cpu'
    lang: str = 'pt'
    idf: bool = False
    rescale: bool = False
    baseline_path: str | None = None
    overflow: Literal['error', 'truncate'] = 'error'
    allow_download: bool = False


class StatsConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bootstrap: int = Field(default=5000, ge=1)
    seed: int = 42
    margin: float = Field(default=0.05, gt=0, allow_inf_nan=False)


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run: RunConfig = Field(default_factory=RunConfig)
    metrics: MetricConfig = Field(default_factory=MetricConfig)
    stats: StatsConfig = Field(default_factory=StatsConfig)


class MetricScore(BaseModel):
    precision: float | None = Field(default=None, allow_inf_nan=False)
    recall: float | None = Field(default=None, allow_inf_nan=False)
    f1: float | None = Field(default=None, allow_inf_nan=False)
    state: Literal['success', 'skipped', 'error'] = 'skipped'
    error: str | None = None
    details: dict = Field(default_factory=dict)


class AttemptResult(BaseModel):
    case_id: str
    repeat_index: int = Field(ge=1)
    attempt_revision: int = Field(default=1, ge=1)
    state: Literal['planned', 'running', 'success', 'error', 'uncertain'] = 'planned'
    rag_status: str | None = None
    answer: str | None = None
    sources: list[dict] = Field(default_factory=list)
    started_at: str | None = None
    ended_at: str | None = None
    duration_seconds: float | None = None
    error_type: str | None = None
    error_message: str | None = None


class ScoredAttempt(BaseModel):
    attempt: AttemptResult
    case: EvalCase
    rouge_l: MetricScore = Field(default_factory=MetricScore)
    bert_score: MetricScore = Field(default_factory=MetricScore)
    judgment: Literal['correct', 'incorrect', 'not_assessed'] = 'not_assessed'
    rationale: str | None = None
    reviewer: str | None = None


class RunManifest(BaseModel):
    schema_version: int = 1
    run_id: str
    identity_hash: str
    selection: DatasetSelection
    run_config: RunConfig
    rag_metadata: dict


class EvaluationSnapshot(BaseModel):
    manifest: RunManifest
    metric_fingerprint: str
    metric_metadata: dict
    results: list[ScoredAttempt]
