from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "sd_local_user"
    s3_secret_key: str = "sd_local_password"

    database_url: str = "postgresql+psycopg://postgres:sd_local@localhost:5432/socio_digital"
    redis_url: str = "redis://localhost:6379/0"
    cookie_secure: bool = True
    allowed_origins: list[str] = ["http://localhost:8000"]

    # Seguranca e Rotacao de Segredos
    app_secret_key: str = Field(
        default="sd_default_secret_dev_key_change_in_prod_1234567890", min_length=16
    )
    hsts_enabled: bool = Field(default=True)

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=120, ge=1)
    rate_limit_ai_per_minute: int = Field(default=20, ge=1)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1)

    qdrant_url: HttpUrl = "http://localhost:6333"
    ollama_url: HttpUrl = "http://localhost:11434"
    embedding_model: str = Field(default="qwen3-embedding:0.6b", min_length=1)
    generation_model: str = Field(default="qwen3:8b", min_length=1)
    collection_name: str = Field(default="knowledge_base", min_length=1, max_length=255)
    embedding_dimensions: int = Field(default=1024, ge=32, le=4096)
    top_k: int = Field(default=8, ge=1, le=10)
    candidate_k: int = Field(default=30, ge=1, le=200)
    # Reforço multiplicativo do RRF para natureza "legislacao"; 0 desliga.
    legislation_boost: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)
    citation_slots: int = Field(default=2, ge=0, le=10)
    score_threshold: float = Field(default=0.5, ge=-1, le=1, allow_inf_nan=False)
    qdrant_timeout: float = Field(default=5, gt=0, le=120, allow_inf_nan=False)
    ollama_timeout: float = Field(default=120, gt=0, le=600, allow_inf_nan=False)
    num_ctx: int = Field(default=8192, ge=8192, le=32768)
    num_predict: int = Field(default=1024, ge=64, le=1024)
    max_context_chars: int = Field(default=12000, ge=1, le=24000)
    reranker_url: HttpUrl | None = None
    reranker_timeout: float = Field(default=10, gt=0, le=120, allow_inf_nan=False)

    @field_validator("reranker_url", mode="before")
    @classmethod
    def optional_reranker(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_embedding_dimensions(self):
        if self.embedding_model == "qwen3-embedding:0.6b" and self.embedding_dimensions != 1024:
            raise ValueError("qwen3-embedding:0.6b requires 1024 dimensions in this application")
        return self
