"""Explicit, transactional PostgreSQL upgrades. No model-driven startup DDL."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text


def settings(connection):
    cfg=Config()
    cfg.set_main_option('script_location',str(Path(__file__).parent))
    cfg.attributes['connection']=connection
    return cfg


def head():
    return ScriptDirectory.from_config(settings(None)).get_current_head()


def verify_schema(connection, metadata, *, check_nullable=True):
    ins=inspect(connection)
    found=set(ins.get_table_names())-{'alembic_version'}
    unexpected=found-set(metadata.tables)
    if unexpected:raise RuntimeError('Schema drift: unexpected tables '+', '.join(sorted(unexpected)))
    missing=set(metadata.tables)-found
    if missing:raise RuntimeError('Schema drift: missing tables '+', '.join(sorted(missing)))
    for table in metadata.sorted_tables:
        actual={c['name']:c for c in ins.get_columns(table.name)}
        if set(actual)!=set(table.columns.keys()):
            raise RuntimeError('Schema drift: columns differ for '+table.name)
        for col in table.columns:
            if check_nullable and actual[col.name]['nullable'] != col.nullable:
                raise RuntimeError('Schema drift: nullability differs for '+table.name+'.'+col.name)
            if actual[col.name]['type']._type_affinity != col.type._type_affinity:
                raise RuntimeError('Schema drift: column type differs for '+table.name+'.'+col.name)
            if getattr(col.type,'length',None) != getattr(actual[col.name]['type'],'length',None):
                raise RuntimeError('Schema drift: column length differs for '+table.name+'.'+col.name)
        if set(ins.get_pk_constraint(table.name)['constrained_columns']) != {c.name for c in table.primary_key}:
            raise RuntimeError('Schema drift: primary key differs for '+table.name)
        fks={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns'])) for f in ins.get_foreign_keys(table.name)}
        for fk in table.foreign_key_constraints:
            expected=(tuple(c.name for c in fk.columns),next(iter(fk.elements)).column.table.name,
                      tuple(e.column.name for e in fk.elements))
            if expected not in fks:raise RuntimeError('Schema drift: foreign key differs for '+table.name)
        indexes={i['name']:(tuple(i['column_names']),i['unique']) for i in ins.get_indexes(table.name)}
        for idx in table.indexes:
            if indexes.get(idx.name)!=(tuple(c.name for c in idx.columns),idx.unique):
                raise RuntimeError('Schema drift: index differs for '+table.name)
        uniques={tuple(u['column_names']) for u in ins.get_unique_constraints(table.name)}
        for constraint in table.constraints:
            if constraint.__class__.__name__=='UniqueConstraint' and tuple(c.name for c in constraint.columns) not in uniques:
                raise RuntimeError('Schema drift: unique constraint differs for '+table.name)


def check(engine):
    from ..models import Base
    with engine.connect() as connection:
        if MigrationContext.configure(connection).get_current_heads() != (head(),):
            raise RuntimeError('Database upgrade required; run the reviewed migration command.')
        verify_schema(connection,Base.metadata)


def upgrade(engine, *, adopt_existing=False):
    with engine.begin() as connection:
        if connection.dialect.name=='postgresql':
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='120s'"))
            if not connection.scalar(text('SELECT pg_try_advisory_xact_lock(734626284)')):
                raise RuntimeError('Another database upgrade is in progress')
        cfg=settings(connection)
        current=MigrationContext.configure(connection).get_current_heads()
        script=ScriptDirectory.from_config(cfg)
        if len(current)>1:raise RuntimeError('Multiple schema revisions require manual review')
        if current:
            script.get_revision(current[0])  # refuse unknown/newer revisions
        elif set(inspect(connection).get_table_names())-{'alembic_version'}:
            if not adopt_existing:raise RuntimeError('Existing unversioned database: explicit adoption required')
            from .baseline_schema import Base
            verify_schema(connection,Base.metadata,check_nullable=False)
            command.stamp(cfg,'0001_baseline')
        command.upgrade(cfg,'head')
        from ..models import Base
        verify_schema(connection,Base.metadata)


def downgrade_index(engine):
    """Only the reviewed index revision is reversible; no table/data teardown command."""
    with engine.begin() as connection:
        if MigrationContext.configure(connection).get_current_heads() != ('0002_audit_index',):
            raise RuntimeError('Unexpected schema revision')
        command.downgrade(settings(connection),'0001_baseline')
