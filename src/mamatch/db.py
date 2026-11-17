from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import Base

_engines: dict[str, object] = {}


def get_engine(url: str | None = None):
    url = url or config.DATABASE_URL
    if url not in _engines:
        if url.startswith("sqlite:///"):
            from pathlib import Path

            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engines[url] = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    return _engines[url]


def init_db(url: str | None = None) -> None:
    """Explicit initialization for CLI/tests. Web startup never mutates schema."""
    from .migrations import upgrade
    upgrade(get_engine(url))


def check_schema(url: str | None = None) -> None:
    from .migrations import check
    check(get_engine(url))


def session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False)


@contextmanager
def session_scope(url: str | None = None) -> Iterator[Session]:
    session = session_factory(url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
