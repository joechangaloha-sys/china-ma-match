"""Run migration and integrity probes ONLY on a generated restored scratch database."""
import re
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url
from . import config
from .migrations import upgrade, check, head


def verify_clone(name):
    original=make_url(config.DATABASE_URL)
    if not re.fullmatch(r'mamatch_restore_[a-f0-9]{16}',name) or name==original.database:
        raise RuntimeError('Refusing any non-scratch database')
    engine=create_engine(original.set(database=name))
    upgrade(engine,adopt_existing=True)
    check(engine)
    with engine.connect() as connection:
        unvalidated=connection.scalar(text("SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace AND NOT convalidated"))
        if unvalidated:raise RuntimeError('Unvalidated constraints after restore')
    # Inject a failing upgrade on the isolated clone; both DDL and revision writes must roll back.
    from unittest.mock import patch
    def failed_upgrade(cfg, target):
        connection=cfg.attributes['connection']
        connection.execute(text('CREATE TABLE recovery_rollback_probe (id integer PRIMARY KEY)'))
        connection.execute(text("UPDATE alembic_version SET version_num='injected_failure'"))
        raise RuntimeError('intentional rollback probe')
    try:
        with patch('mamatch.migrations.command.upgrade',side_effect=failed_upgrade):
            upgrade(engine)
    except RuntimeError as exc:
        if str(exc)!='intentional rollback probe':raise
    check(engine)
    with engine.connect() as connection:
        if connection.scalar(text("SELECT to_regclass('public.recovery_rollback_probe')")):
            raise RuntimeError('DDL rollback failed')
        for table in inspect(connection).get_table_names():
            if table=='alembic_version':continue
            # Every serial sequence must be ahead of the restored primary-key maximum.
            for col in inspect(connection).get_columns(table):
                default=col.get('default') or ''
                if 'nextval(' not in default:continue
                seq=connection.scalar(text('SELECT pg_get_serial_sequence(:t,:c)'),{'t':table,'c':col['name']})
                if not seq:continue
                if not re.fullmatch(r'[a-z0-9_.]+',seq):raise RuntimeError('Unexpected sequence identifier')
                last=connection.scalar(text('SELECT last_value FROM '+seq))
                maximum=connection.scalar(text(f'SELECT max("{col["name"]}") FROM "{table}"'))
                if maximum is not None and last<maximum:raise RuntimeError('Restored sequence is behind its data')
    # Live pilot may have zero uploads; exercise the same exporter with disposable file bytes too.
    import hashlib, io, tarfile, tempfile
    from pathlib import Path
    from .recovery_files import export_referenced
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'fixture.txt';body=b'Fictional document recovery fixture';path.write_bytes(body)
        output=io.BytesIO()
        export_referenced([{'path':str(path),'sha256':hashlib.sha256(body).hexdigest()}],folder,output)
        with tarfile.open(fileobj=io.BytesIO(output.getvalue())) as archive:
            if archive.extractfile('fixture.txt').read()!=body:raise RuntimeError('Synthetic file recovery failed')
    print('Isolated migration, constraints, sequences, file bytes and DDL rollback passed at '+head())
    engine.dispose()


if __name__=='__main__':
    verify_clone(sys.argv[1])
