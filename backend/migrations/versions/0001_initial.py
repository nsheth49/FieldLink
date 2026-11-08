"""Initial schema, optional Timescale partitioning on the identity time column."""
from alembic import op
from sqlalchemy import text
from app.db.models import Base
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind(); Base.metadata.create_all(bind)
    if bind.dialect.name=='postgresql':
        available=bind.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='timescaledb')"))
        if available:
            # Integer epoch is a supported Timescale partition column; identity includes ts.
            bind.execute(text('ALTER TABLE telemetry ALTER COLUMN ts TYPE BIGINT USING ts::bigint'))
            bind.execute(text("SELECT create_hypertable('telemetry','ts',chunk_time_interval=>604800,if_not_exists=>TRUE)"))

def downgrade(): raise RuntimeError('Destructive downgrade disabled; restore from backup')
