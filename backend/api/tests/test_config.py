import pytest
from app.config import Settings
from app.schemas import QueryRequest
from pydantic import ValidationError


@pytest.mark.parametrize("question", ["", " \n ", "x" * 2001])
def test_rejects_invalid_question(question):
    with pytest.raises(ValidationError):
        QueryRequest(question=question)


def test_question_is_trimmed():
    assert QueryRequest(question="  Como funciona?  ").question == "Como funciona?"


@pytest.mark.parametrize(
    "values",
    [
        {"top_k": 0},
        {"top_k": 11},
        {"embedding_dimensions": 512},
        {"ollama_url": "ftp://localhost"},
        {"qdrant_url": "arquivo"},
        {"qdrant_timeout": 0},
        {"ollama_timeout": -1},
        {"score_threshold": 1.1},
        {"max_context_chars": 500000},
        {"num_ctx": 1024},
        {"collection_name": ""},
    ],
)
def test_rejects_incompatible_configuration(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_empty_reranker_url_disables_optional_gpu_service():
    assert Settings(reranker_url="").reranker_url is None


def test_legislation_boost_padrao_e_limites():
    assert Settings().legislation_boost > 0
    with pytest.raises(ValidationError):
        Settings(legislation_boost=-1)


def test_rerank_boost_e_janela_desligados_por_padrao():
    settings = Settings()
    assert settings.rerank_legislation_boost == 0
    assert settings.context_window_chars == 0
    with pytest.raises(ValidationError):
        Settings(rerank_legislation_boost=-0.1)
    with pytest.raises(ValidationError):
        Settings(context_window_chars=8001)


def test_max_trechos_por_documento_desligado_por_padrao():
    assert Settings().max_trechos_por_documento == 0
    with pytest.raises(ValidationError):
        Settings(max_trechos_por_documento=-1)
