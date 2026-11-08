from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from backend.app.config import DATABASE_URL
from backend.app.db.base import Base
from backend.app.db.models import (
    Event,
    EventAuditLog,
    Geofence,
    MonitoringSession,
    Snapshot,
    SystemMetric,
    VideoSource,
)
from backend.app.db.session import create_database_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = config.get_main_option("sqlalchemy.url") or DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_database_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
