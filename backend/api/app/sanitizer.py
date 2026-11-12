from __future__ import annotations

import logging
import re
from typing import Any

# Padrões canônicos de Dados Pessoais Identificáveis (PII) e empresariais sensíveis (LGPD)
CPF_REGEX = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
CNPJ_REGEX = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX = re.compile(r"(?:\+?55\s?)?(?:\(?0?[1-9]{2}\)?\s?)?(?:9\s?\d{4}|\d{4})[-.\s]?\d{4}\b")
TOKEN_BEARER_REGEX = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9_\-\.]{15,}\b")

SENSITIVE_KEYS = {
    "password",
    "senha",
    "secret",
    "secret_key",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "cpf",
    "cnpj",
    "faturamento",
    "faturamento_anual",
    "folha",
    "folha_anual",
}


def sanitize_text(text: str) -> str:
    """
    Substitui padrões de PII (CPF, CNPJ, e-mail, telefone e tokens) por máscaras anônimas.
    Conforme preconizado pelo Art. 12 da Lei 13.709/2018 (LGPD).
    """
    if not isinstance(text, str):
        return text

    sanitized = CPF_REGEX.sub("[CPF REDIGIDO]", text)
    sanitized = CNPJ_REGEX.sub("[CNPJ REDIGIDO]", sanitized)
    sanitized = EMAIL_REGEX.sub("[EMAIL REDIGIDO]", sanitized)
    sanitized = PHONE_REGEX.sub("[TELEFONE REDIGIDO]", sanitized)
    sanitized = TOKEN_BEARER_REGEX.sub(r"\1[TOKEN REDIGIDO]", sanitized)
    return sanitized


def sanitize_dict(data: Any) -> Any:
    """
    Higieniza dicionários e estruturas recursivas para serialização em logs ou exportação.
    """
    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            key_lower = str(k).lower()
            if any(s in key_lower for s in ("password", "senha", "secret", "token", "auth")):
                cleaned[k] = "[CONFIDENCIAL]"
            elif key_lower in ("cpf", "cnpj"):
                cleaned[k] = "[DADO IDENTIFICADOR REDIGIDO]"
            elif isinstance(v, (dict, list)):
                cleaned[k] = sanitize_dict(v)
            elif isinstance(v, str):
                cleaned[k] = sanitize_text(v)
            else:
                cleaned[k] = v
        return cleaned
    elif isinstance(data, list):
        return [sanitize_dict(item) for item in data]
    elif isinstance(data, str):
        return sanitize_text(data)
    return data


class LGPDSanitizingFormatter(logging.Formatter):
    """
    Formatter customizado para a biblioteca logging do Python.
    Intercepta todas as mensagens de log antes de irem para stdout/stderr ou arquivo,
    garantindo que nenhum dado sensível de sócio, MEI ou empresa vaze para logs de infraestrutura.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Sanitiza a mensagem principal
        if isinstance(record.msg, str):
            record.msg = sanitize_text(record.msg)

        # Sanitiza argumentos se presentes
        if record.args:
            if isinstance(record.args, dict):
                record.args = sanitize_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_text(a)
                    if isinstance(a, str)
                    else sanitize_dict(a)
                    if isinstance(a, (dict, list))
                    else a
                    for a in record.args
                )

        return super().format(record)
