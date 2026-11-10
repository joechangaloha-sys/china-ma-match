"""Frozen current-schema baseline; existing databases require explicit verified adoption."""
from alembic import op
from mamatch.migrations.baseline_schema import Base
revision = '0001_baseline'
down_revision = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError('Baseline downgrade would destroy records; restore only to an isolated database.')
