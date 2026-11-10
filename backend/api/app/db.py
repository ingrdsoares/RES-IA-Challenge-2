from collections.abc import Iterator
from importlib import import_module

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def session_factory(url: str):
    # Every process (API, worker and CLI) needs the complete FK metadata graph.
    for module in (
        "access",
        "companies",
        "jobs",
        "legal",
        "assistant",
        "evidence",
        "tasks",
        "fiscal",
    ):
        import_module(f"app.{module}.models")
    return sessionmaker(create_engine(url, pool_pre_ping=True), expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.db_factory() as db:
        yield db
