import io
import logging

from app.main import create_app
from app.sanitizer import (
    LGPDSanitizingFormatter,
    sanitize_dict,
    sanitize_text,
)
from starlette.testclient import TestClient


def test_sanitize_text_cpf():
    raw = "O sócio tem CPF 123.456.789-00 e solicitou cálculo de DAS."
    sanitized = sanitize_text(raw)
    assert "123.456.789-00" not in sanitized
    assert "[CPF REDIGIDO]" in sanitized


def test_sanitize_text_cnpj():
    raw = "A empresa possui CNPJ 12.345.678/0001-90 cadastrado no Simples."
    sanitized = sanitize_text(raw)
    assert "12.345.678/0001-90" not in sanitized
    assert "[CNPJ REDIGIDO]" in sanitized


def test_sanitize_text_email_and_phone():
    raw = "Contato do titular: maria.silva@empresa.com.br ou (11) 98765-4321."
    sanitized = sanitize_text(raw)
    assert "maria.silva@empresa.com.br" not in sanitized
    assert "[EMAIL REDIGIDO]" in sanitized
    assert "98765-4321" not in sanitized
    assert "[TELEFONE REDIGIDO]" in sanitized


def test_sanitize_text_token_bearer():
    raw = "Requisição autorizada com Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz."
    sanitized = sanitize_text(raw)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "[TOKEN REDIGIDO]" in sanitized


def test_sanitize_dict_sensitive_keys():
    payload = {
        "usuario": "Carlos MEI",
        "email": "carlos@mei.com.br",
        "cpf": "111.222.333-44",
        "senha": "super_secret_password_123",
        "detalhes": {"token": "secret_token_abc", "faturamento_anual": 75000.0},
    }
    cleaned = sanitize_dict(payload)
    assert cleaned["senha"] == "[CONFIDENCIAL]"
    assert cleaned["cpf"] == "[DADO IDENTIFICADOR REDIGIDO]"
    assert cleaned["detalhes"]["token"] == "[CONFIDENCIAL]"
    assert "[EMAIL REDIGIDO]" in cleaned["email"]


def test_lgpd_formatter_redacts_logs():
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(LGPDSanitizingFormatter("%(levelname)s - %(message)s"))

    logger = logging.getLogger("test_lgpd_logger")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("Processando empresa CNPJ 98.765.432/0001-10 de socio CPF 999.888.777-66")
    handler.flush()

    output = log_stream.getvalue()
    assert "98.765.432/0001-10" not in output
    assert "999.888.777-66" not in output
    assert "[CNPJ REDIGIDO]" in output
    assert "[CPF REDIGIDO]" in output


def test_request_id_in_response_headers():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    # 1. Sem passar X-Request-ID (gera automático)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 10

    # 2. Passando X-Request-ID personalizado
    custom_id = "custom-trace-id-12345"
    resp2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp2.status_code == 200
    assert resp2.headers["X-Request-ID"] == custom_id
