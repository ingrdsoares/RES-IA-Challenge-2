from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    qdrant_url: HttpUrl = "http://localhost:6333"
    ollama_url: HttpUrl = "http://localhost:11434"
    embedding_model: str = Field(default="qwen3-embedding:0.6b", min_length=1)
    generation_model: str = Field(default="qwen3:8b", min_length=1)
    collection_name: str = Field(default="knowledge_base", min_length=1, max_length=255)
    embedding_dimensions: int = Field(default=1024, ge=32, le=4096)
    top_k: int = Field(default=5, ge=1, le=10)
    candidate_k: int = Field(default=30, ge=1, le=200)
    citation_slots: int = Field(default=2, ge=0, le=10)
    score_threshold: float = Field(default=0.5, ge=-1, le=1, allow_inf_nan=False)
    qdrant_timeout: float = Field(default=5, gt=0, le=120, allow_inf_nan=False)
    ollama_timeout: float = Field(default=120, gt=0, le=600, allow_inf_nan=False)
    num_ctx: int = Field(default=8192, ge=8192, le=32768)
    num_predict: int = Field(default=1024, ge=64, le=1024)
    max_context_chars: int = Field(default=12000, ge=1, le=24000)
    reranker_url: HttpUrl | None = None
    reranker_timeout: float = Field(default=10, gt=0, le=120, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_embedding_dimensions(self):
        if self.embedding_model == "qwen3-embedding:0.6b" and self.embedding_dimensions != 1024:
            raise ValueError("qwen3-embedding:0.6b requires 1024 dimensions in this application")
        return self
