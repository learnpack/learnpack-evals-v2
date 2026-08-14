"""Alembic environment.

The schema is written by hand in the revisions (there is no declarative metadata to
autogenerate from: repositories map aggregates explicitly, keeping the domain free of
SQLAlchemy — ARCHITECTURE.md §1).
"""

from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.config import get_settings

config = context.config

if config.config_file_name is not None:
    # `disable_existing_loggers=False` because this runs in-process too: the test suite
    # migrates at session start (`tests/conftest.py`), and the default would switch OFF every
    # application logger created before that — silencing the whole suite's warnings, this
    # module's schema check included, for the rest of the run.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = None


def _database_url() -> str:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see backend/.env.example)")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
