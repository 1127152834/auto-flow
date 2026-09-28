from alembic import context
from sqlalchemy import engine_from_config, pool

from autoflow.infrastructure.database import (  # noqa: F401
    android_models,
    environment_models,
    project_automation_models,
    project_data_models,
    project_data_status_batch_models,
    project_excel_models,
    project_run_models,
    project_sync_models,
    proxy_models,
    workflow_core_models,
    workflow_models,
    workflow_runtime_models,
)
from autoflow.infrastructure.database.models import Base

config = context.config
target_metadata = Base.metadata


def include_object(object_: object, name: str | None, type_: str, reflected: bool, compare_to: object | None) -> bool:
    # Preserved migration-only history, not current ORM-owned data. Do not
    # autogenerate destructive drops merely because those features retired.
    return not (
        reflected and compare_to is None and type_ == "table"
        and name in {"android_operations", "project_workflow_debug_commands"}
    )


def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # sqlite3 legacy transaction mode does not BEGIN for DDL. Keep schema
        # changes and alembic_version atomic, including failed first launches.
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
