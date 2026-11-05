from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.errors import CollectionIncompatible, DependencyTimeout, DependencyUnavailable, QueryBusy
from app.models import LocalModels
from app.rag import RagService
from app.schemas import QueryRequest, QueryResponse
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, service: RagService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings if settings is not None else Settings()
        rag = service if service is not None else RagService(config, VectorStore(config), LocalModels(config))
        app.state.rag = rag
        try:
            try:
                await run_in_threadpool(rag.store.ensure_collection)
            except DependencyUnavailable:
                logger.warning("Qdrant indisponível ou coleção incompatível; consulte /ready.")
            yield
        finally:
            await run_in_threadpool(rag.close)

    app = FastAPI(
        title="Sócio Digital — RAG", description="Consulta de documentos com Qwen e Qdrant.",
        lifespan=lifespan,
    )

    @app.exception_handler(DependencyUnavailable)
    async def dependency_error(request: Request, exc: DependencyUnavailable):
        status, detail = 503, "Um serviço necessário ao RAG está indisponível. Consulte /ready e os logs."
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
            raise HTTPException(503, "Qdrant, coleção ou modelos Ollama não estão prontos.") from None
        return {"status": "ready"}

    @app.post("/rag/query", response_model=QueryResponse)
    def query(payload: QueryRequest, request: Request):
        return request.app.state.rag.query(payload.question)

    return app


app = create_app()
