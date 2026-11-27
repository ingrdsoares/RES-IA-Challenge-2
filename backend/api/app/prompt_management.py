"""Langfuse prompt retrieval and content-free observability."""

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache, wraps

from langfuse import Langfuse
from langfuse.model import TextPromptClient
from opentelemetry.sdk.trace import TracerProvider

from app.errors import DependencyUnavailable

logger = logging.getLogger(__name__)
_catalog = ContextVar("langfuse_prompt_catalog", default=None)


@cache
def client():
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return None
    return Langfuse(tracer_provider=TracerProvider())


class PromptUnavailable(DependencyUnavailable):
    """A required Langfuse prompt could not be resolved or compiled."""


@dataclass(frozen=True)
class ManagedPrompt:
    text: str
    remote: TextPromptClient

    @property
    def version(self) -> str:
        return str(self.remote.version)


def load_prompt(name: str, **variables: str) -> ManagedPrompt:
    try:
        sdk = client()
        if sdk is None:
            raise RuntimeError("Credenciais ausentes")
        catalog = _catalog.get()
        remote = catalog.get(name) if catalog is not None else None
        if remote is None:
            remote = sdk.get_prompt(name, label="production", type="text")
        if not isinstance(remote, TextPromptClient) or set(remote.variables) != variables.keys():
            raise ValueError("Contrato de variáveis incompatível")
        text = remote.compile(**variables)
        if catalog is not None:
            catalog[name] = remote
        return ManagedPrompt(text, remote)
    except Exception:
        raise PromptUnavailable(f"Prompt indisponível no Langfuse: {name}.") from None


@contextmanager
def observation(name, **kwargs):
    try:
        sdk = client()
        context = sdk.start_as_current_observation(name=name, **kwargs) if sdk else None
        span = context.__enter__() if context is not None else None
    except Exception:
        logger.warning("Não foi possível iniciar a observação no Langfuse.")
        context, span = None, None
    try:
        yield span
    except BaseException as error:
        # No exception object reaches OpenTelemetry, even on cancellation.
        update_observation(span, level="ERROR", status_message=type(error).__name__)
        raise
    finally:
        if context is not None:
            try:
                context.__exit__(None, None, None)
            except Exception:
                logger.warning("Não foi possível encerrar a observação no Langfuse.")


def update_observation(span, **kwargs):
    if span is not None:
        try:
            span.update(**kwargs)
        except Exception:
            logger.warning("Não foi possível atualizar a observação no Langfuse.")


@contextmanager
def prompt_scope():
    token = _catalog.set({}) if _catalog.get() is None else None
    try:
        yield
    finally:
        if token is not None:
            _catalog.reset(token)


def traced(name, *, as_type="span"):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            with prompt_scope(), observation(name, as_type=as_type):
                return function(*args, **kwargs)

        return run

    return decorate


def flush():
    try:
        sdk = client()
        if sdk is not None:
            sdk.flush()
    except Exception:
        logger.warning("Não foi possível exportar as observações ao Langfuse.")
