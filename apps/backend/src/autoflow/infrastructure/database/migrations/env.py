from alembic import context
from sqlalchemy import engine_from_config, pool

from autoflow.infrastructure.database import project_data_models  # noqa: F401
from autoflow.infrastructure.database.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # sqlite3 legacy transaction mode does not BEGIN for DDL. Keep schema
        # changes and alembic_version atomic, including failed first launches.
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
