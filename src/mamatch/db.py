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
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)


def _add_missing_columns(engine) -> None:
    """Additive migration for local databases: new model columns are added with their defaults.

    Enough for the MVP's SQLite files; switch to Alembic before any production deployment.
    """
    import json

    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                default = col.default.arg if col.default is not None else None
                if callable(default):
                    # JSON columns default to list() or dict(); SQLAlchemy wraps them to take a context.
                    # Other callables (random ids) must not give every old row the same value.
                    if col.type.__class__.__name__ == "JSON":
                        literal = "'" + json.dumps(default(None)) + "'"
                    else:
                        literal = "NULL"
                elif isinstance(default, bool):
                    literal = "1" if default else "0"
                elif isinstance(default, (int, float)):
                    literal = str(default)
                elif isinstance(default, str):
                    literal = "'" + default.replace("'", "''") + "'"
                else:
                    literal = "NULL"
                coltype = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype} DEFAULT {literal}'))


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
