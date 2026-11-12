from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.access.models import Account
from app.config import Settings
from app.db import Base, get_db
from app.dependencies import require_account
from app.main import create_app
from app.telemetria import service
from app.telemetria.models import AvaliacaoRag, ConsultaRag
from app.telemetria.router import router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(
        engine, tables=[Account.__table__, ConsultaRag.__table__, AvaliacaoRag.__table__]
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    conta = Account(id=uuid4(), email="admin@x.com", password_hash="x")
    with factory() as db:
        db.add(conta)
        db.commit()
    app = FastAPI()
    app.include_router(router)

    def _db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_account] = lambda: conta
    app.state.settings = Settings(admin_emails="admin@x.com")
    return SimpleNamespace(client=TestClient(app), factory=factory, app=app, conta=conta)


def _consulta(factory, rid, status, ms, dia=10):
    service.registrar(factory, rid, status, ms, 1, "kb")
    with factory() as db:
        c = db.scalar(select(ConsultaRag).where(ConsultaRag.request_id == rid))
        c.created_at = datetime(2026, 11, dia, 12, tzinfo=UTC)
        db.commit()


def test_metricas_agrega_por_dia_e_status(env):
    for i, ms in enumerate([100, 200, 300, 400, 1000]):
        _consulta(env.factory, f"r{i}", "answered", ms)
    _consulta(env.factory, "e", "error", 50, dia=11)
    r = env.client.get("/rag/metricas", params={"from": "2026-11-10", "to": "2026-11-11"})
    assert r.status_code == 200
    d10, d11 = r.json()["days"]
    assert d10 == {
        "date": "2026-11-10",
        "total": 5,
        "by_status": {"answered": 5},
        "latency_ms_median": 300,
        "latency_ms_p95": 880,
    }
    assert d11["by_status"] == {"error": 1} and d11["latency_ms_p95"] == 50


def test_metricas_exige_admin_e_intervalo_valido(env, monkeypatch):
    params = {"from": "2026-11-10", "to": "2026-11-11"}
    assert (
        env.client.get(
            "/rag/metricas", params={"from": "2026-11-11", "to": "2026-11-10"}
        ).status_code
        == 422
    )
    env.app.state.settings = Settings(admin_emails="outro@x.com")
    assert env.client.get("/rag/metricas", params=params).status_code == 403


def test_feedback_upsert_e_validacoes(env):
    _consulta(env.factory, "rid", "answered", 10)
    post = env.client.post
    assert (
        post("/rag/feedback", json={"request_id": "nao-existe", "useful": True}).status_code == 404
    )
    assert (
        post(
            "/rag/feedback", json={"request_id": "rid", "useful": False, "reason": "xyz"}
        ).status_code
        == 422
    )
    assert (
        post(
            "/rag/feedback",
            json={"request_id": "rid", "useful": False, "reason": "incorreta", "text": "oi"},
        ).status_code
        == 422
    )
    assert (
        post(
            "/rag/feedback", json={"request_id": "rid", "useful": False, "reason": "incorreta"}
        ).status_code
        == 204
    )
    assert (
        post(
            "/rag/feedback", json={"request_id": "rid", "useful": True, "reason": "incorreta"}
        ).status_code
        == 204
    )
    with env.factory() as db:
        (a,) = db.scalars(select(AvaliacaoRag)).all()
    assert a.useful is True and a.reason is None


def test_rag_query_registra_telemetria_sem_conteudo(service, monkeypatch):
    chamadas = []
    monkeypatch.setattr("app.main.registrar", lambda *a: chamadas.append(a))
    app = create_app(service=service)
    app.dependency_overrides[require_account] = lambda: object()
    with TestClient(app) as client:
        r = client.post("/rag/query", json={"question": "Segredo 123.456.789-09?"})
    assert r.status_code == 200
    (_, rid, status, ms, fontes, colecao) = chamadas[0]
    assert (status, fontes, colecao) == ("empty_knowledge_base", 0, "knowledge_base")
    assert rid == r.headers["X-Request-ID"] and ms >= 0
    assert "123.456.789" not in repr(chamadas)


def test_registrar_engole_falha():
    def quebrado():
        raise RuntimeError("db fora")

    service.registrar(quebrado, "r", "answered", 1, 0, "kb")
