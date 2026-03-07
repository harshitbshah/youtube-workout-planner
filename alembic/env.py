import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all models so Alembic can detect them for autogenerate
import api.models  # noqa: F401
from api.database import Base

config = context.config
# Only set URL from env if not already set programmatically (e.g. by integration tests)
if not config.get_main_option("sqlalchemy.url", default=None):
    config.set_main_option(
        "sqlalchemy.url",
        os.getenv("DATABASE_URL", "postgresql://localhost/workout_planner"),
    )

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
