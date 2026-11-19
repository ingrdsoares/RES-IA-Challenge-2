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


def test_esclarecimento_modelo_desligado_por_padrao():
    assert Settings().esclarecimento_modelo is False


def test_peso_expansao_padrao_e_limites():
    assert Settings().peso_expansao == 0.5
    with pytest.raises(ValidationError):
        Settings(peso_expansao=1.5)


@pytest.mark.parametrize(
    "url",
    ["", "http://example.com", "https://localhost", "https://127.0.0.1", "https://example.com/#x"],
)
def test_external_smtp_requires_explicit_public_frontend(url):
    with pytest.raises(ValueError, match="FRONTEND_URL"):
        Settings(smtp_host="smtp.example.com", frontend_url=url)


def test_reset_delivery_settings():
    assert Settings(smtp_host="", frontend_url="").frontend_url is None
    local = Settings(smtp_host="mailpit", smtp_starttls=False, frontend_url="")
    assert str(local.frontend_url) == "http://localhost:3000/"
    external = Settings(smtp_host="smtp.example.com", frontend_url="https://fiscal.example.com")
    assert str(external.frontend_url) == "https://fiscal.example.com/"
    with pytest.raises(ValueError, match="STARTTLS"):
        Settings(smtp_host="smtp.example.com", smtp_starttls=False)


def test_provedor_padrao_e_ollama():
    assert Settings().llm_provider == "ollama"


@pytest.mark.parametrize("provedor", ["google", "deepseek"])
def test_provedor_de_nuvem_exige_chave(provedor):
    with pytest.raises(ValidationError):
        Settings(llm_provider=provedor)
    assert Settings(llm_provider=provedor, **{f"{provedor}_api_key": "k"}).llm_provider == provedor


def test_chave_nao_aparece_no_repr():
    settings = Settings(llm_provider="google", google_api_key="segredo")
    assert "segredo" not in repr(settings)
    with pytest.raises(ValidationError) as erro:
        Settings(llm_provider="deepseek", google_api_key="segredo")
    assert "segredo" not in str(erro.value)
