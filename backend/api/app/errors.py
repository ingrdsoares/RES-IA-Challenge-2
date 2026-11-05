class DependencyUnavailable(Exception):
    """A required service cannot complete the operation."""


class DependencyTimeout(DependencyUnavailable):
    """A required service exceeded its time budget."""


class CollectionIncompatible(DependencyUnavailable):
    """Existing collection cannot be queried using this configuration."""
from contextlib import contextmanager

import httpx
import ollama
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse




@contextmanager
def dependency_errors(service: str):
    try:
        yield
    except httpx.TimeoutException as exc:
        raise DependencyTimeout(f"Tempo de espera excedido: {service}.") from exc
    except ResponseHandlingException as exc:
        if isinstance(exc.source, httpx.TimeoutException):
            raise DependencyTimeout(f"Tempo de espera excedido: {service}.") from exc
        raise DependencyUnavailable(f"Serviço indisponível: {service}.") from exc
    except (httpx.HTTPError, UnexpectedResponse, ollama.ResponseError, ConnectionError, ValueError) as exc:
        raise DependencyUnavailable(f"Não foi possível consultar {service}.") from exc
