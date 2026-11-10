import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis import Redis
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.access.router import router as access_router
from app.assistant.router import router as assistant_router
from app.companies.router import router as companies_router
from app.config import Settings
from app.db import session_factory
from app.dependencies import require_account
from app.errors import CollectionIncompatible, DependencyTimeout, DependencyUnavailable, QueryBusy
from app.evidence.router import router as evidence_router
from app.jobs.router import router as jobs_router
from app.legal.router import router as legal_router
from app.models import LocalModels
from app.rag import RagService
from app.schemas import QueryRequest, QueryResponse
from app.tasks.router import router as tasks_router
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, service: RagService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings if settings is not None else Settings()
        rag = (
            service
            if service is not None
            else RagService(config, VectorStore(config), LocalModels(config))
        )
        app.state.settings = config
        app.state.db_factory = session_factory(config.database_url)
        app.state.redis = Redis.from_url(config.redis_url, socket_timeout=3)
        app.state.rag = rag
        try:
            try:
                await run_in_threadpool(rag.store.ensure_collection)
            except DependencyUnavailable:
                logger.warning("Qdrant indisponível ou coleção incompatível; consulte /ready.")
            yield
        finally:
            await run_in_threadpool(rag.close)
            app.state.redis.close()
            app.state.db_factory.kw["bind"].dispose()

    app = FastAPI(
        title="Sócio Digital - Copiloto de Gestão Fiscal",
        description=(
            "Aproximadamente 95% a 99% das empresas ativas no Brasil são micro e pequenos "
            "negócios. A falta de formação contábil gera dependência cega do contador e "
            "terror fiscal nos empreendedores. O Sócio Digital é uma aplicação inteligente "
            "de copiloto fiscal. Consulta de documentos com Qwen e Qdrant."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(access_router)
    app.include_router(companies_router)
    app.include_router(jobs_router)
    app.include_router(legal_router)
    app.include_router(assistant_router)
    app.include_router(evidence_router)
    app.include_router(tasks_router)

    legacy_paths = {"/health", "/ready", "/rag/query"}

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if request.url.path in legacy_paths:
            return await request_validation_exception_handler(request, exc)
        fields = [
            {"field": ".".join(str(p) for p in error["loc"]), "code": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Dados inválidos",
                    "fields": fields,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if request.url.path in legacy_paths:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
            )
        codes = {
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "invalid_input",
            429: "rate_limited",
            503: "unavailable",
        }
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": codes.get(exc.status_code, "request_failed"),
                    "message": exc.detail,
                    "fields": [],
                }
            },
        )

    @app.exception_handler(DependencyUnavailable)
    async def dependency_error(request: Request, exc: DependencyUnavailable):
        status, detail = (
            503,
            "Um serviço necessário ao RAG está indisponível. Consulte /ready e os logs.",
        )
        if isinstance(exc, DependencyTimeout):
            status, detail = 504, "Tempo de espera excedido ao consultar um serviço do RAG."
        elif isinstance(exc, CollectionIncompatible):
            detail = "A coleção vetorial é incompatível com a configuração do backend."
        elif isinstance(exc, QueryBusy):
            detail = "Já existe uma consulta em andamento. Tente novamente após sua conclusão."
        logger.warning("Falha de dependência na rota %s: %s", request.url.path, type(exc).__name__)
        return JSONResponse(status_code=status, content={"detail": detail})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready(request: Request):
        try:
            request.app.state.rag.ready()
        except DependencyUnavailable:
            raise HTTPException(
                503, "Qdrant, coleção ou modelos Ollama não estão prontos."
            ) from None
        return {"status": "ready"}

    @app.post("/rag/query", response_model=QueryResponse, dependencies=[Depends(require_account)])
    def query(payload: QueryRequest, request: Request):
        return request.app.state.rag.query(payload.question)

    return app


app = create_app()
