from alembic import context
from app.db import engine
from app.db.models import Base
with engine.connect() as connection:
    context.configure(connection=connection,target_metadata=Base.metadata)
    with context.begin_transaction(): context.run_migrations()
