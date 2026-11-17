import sqlite3
import pytest
from sqlalchemy import inspect,text
from mamatch import db
from mamatch.migrations import check,upgrade,head,downgrade_index
from mamatch.migrations.baseline_schema import Base as Baseline


def test_partial_legacy_database_requires_review_and_is_not_modified(tmp_path):
    path=tmp_path/'old.db'
    con=sqlite3.connect(path)
    con.execute('CREATE TABLE buyers (id INTEGER PRIMARY KEY, name VARCHAR(200))')
    con.execute("INSERT INTO buyers VALUES (1,'原始记录')");con.commit();con.close()
    engine=db.get_engine(f'sqlite:///{path}')
    with pytest.raises(RuntimeError,match='adoption required'):upgrade(engine)
    with pytest.raises(RuntimeError,match='missing tables'):upgrade(engine,adopt_existing=True)
    assert [c['name'] for c in inspect(engine).get_columns('buyers')]==['id','name']
    with engine.connect() as c:assert c.scalar(text('SELECT name FROM buyers'))=='原始记录'


def test_explicit_baseline_adoption_preserves_records(tmp_path):
    engine=db.get_engine(f'sqlite:///{tmp_path/"baseline.db"}')
    Baseline.metadata.create_all(engine)
    with engine.begin() as c:c.execute(text("INSERT INTO adviser_firms (id,name,city,created_at) VALUES (1,'原始顾问','上海','2026-10-31')"))
    with pytest.raises(RuntimeError,match='adoption required'):upgrade(engine)
    upgrade(engine,adopt_existing=True);check(engine)
    with engine.connect() as c:
        assert c.scalar(text('SELECT name FROM adviser_firms'))=='原始顾问'
        assert c.scalar(text('SELECT version_num FROM alembic_version'))==head()


def test_fresh_upgrades_idempotence_and_reversible_index(db_url):
    engine=db.get_engine(db_url);check(engine);upgrade(engine);check(engine)
    assert 'ix_audit_events_created_at' in {i['name'] for i in inspect(engine).get_indexes('audit_events')}
    downgrade_index(engine)
    with pytest.raises(RuntimeError,match='upgrade required'):check(engine)
    upgrade(engine);check(engine)


def test_unknown_revision_and_schema_drift_fail_closed(db_url):
    engine=db.get_engine(db_url)
    with engine.begin() as c:c.execute(text("UPDATE alembic_version SET version_num='unknown_future'"))
    with pytest.raises(Exception):upgrade(engine)
    with pytest.raises(RuntimeError):check(engine)
    with engine.begin() as c:
        c.execute(text('UPDATE alembic_version SET version_num=:v'),{'v':head()})
        c.execute(text('ALTER TABLE buyers ADD COLUMN unreviewed_column INTEGER'))
    with pytest.raises(RuntimeError,match='columns differ'):check(engine)
    with pytest.raises(RuntimeError,match='columns differ'):upgrade(engine)


def test_web_startup_does_not_initialise_missing_database(tmp_path):
    engine=db.get_engine(f'sqlite:///{tmp_path/"empty.db"}')
    with pytest.raises(RuntimeError,match='upgrade required'):check(engine)
    assert inspect(engine).get_table_names()==[]
