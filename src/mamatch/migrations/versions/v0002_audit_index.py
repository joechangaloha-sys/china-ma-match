"""Index the audit timeline used by the operator workspace."""
from alembic import op
from sqlalchemy import inspect, text
from mamatch.migrations.baseline_schema import Base
revision = '0002_audit_index'
down_revision = '0001_baseline'


def upgrade():
    connection=op.get_bind()
    for table in Base.metadata.sorted_tables:
        actual={c['name']:c for c in inspect(connection).get_columns(table.name)}
        for col in table.columns:
            if not col.nullable and actual[col.name]['nullable']:
                if connection.scalar(text(f'SELECT count(*) FROM "{table.name}" WHERE "{col.name}" IS NULL')):
                    raise RuntimeError('Null values require reviewed repair: '+table.name+'.'+col.name)
                op.alter_column(table.name,col.name,existing_type=col.type,nullable=False)
    op.create_index('ix_audit_events_created_at','audit_events',['created_at'],unique=False)


def downgrade():
    op.drop_index('ix_audit_events_created_at',table_name='audit_events')
