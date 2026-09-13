from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.runs import RunRecord
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import (
    SqlAlchemyWorkflowRunRepository,
)


def _record(run_id=None, request_hash="request"):
    return RunRecord(request_hash, {
        "runId": run_id or str(uuid4()), "workflowId": str(uuid4()),
        "startedAt": datetime.now(UTC).isoformat(), "latestSeq": 1, "state": "starting",
    })


def test_m2_migration_upgrades_m1_and_keeps_existing_workflow(tmp_path):
    database = tmp_path / "workspace.sqlite3"
    config = Config(str(Path("src/autoflow/infrastructure/database/alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "0005_workflow_documents")
    factory = create_session_factory(database)
    with factory.begin() as session:
        session.execute(text("INSERT INTO workflow_documents (id,name,document,layout,revision,created_at,updated_at) VALUES (:id,'kept','{}','{}',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id": str(uuid4())})
    migrate_database(database)
    migrate_database(database)
    with factory() as session:
        assert session.execute(text("SELECT name FROM workflow_documents")).scalar() == "kept"
        assert session.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0010_android_fleet"
    assert {"workflow_runs", "workflow_run_events"} <= set(inspect(factory.kw["bind"]).get_table_names())
    factory.dispose()


def test_database_enforces_one_active_run_across_repository_instances(tmp_path):
    database = tmp_path / "workspace.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    barrier = Barrier(2)

    def attempt(_index):
        repository = SqlAlchemyWorkflowRunRepository(factory)
        record = _record()
        barrier.wait(timeout=3)
        try:
            return repository.create(record)
        except WorkflowError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    saved = [item for item in results if isinstance(item, RunRecord)]
    failed = [item for item in results if isinstance(item, WorkflowError)]
    assert len(saved) == len(failed) == 1
    assert failed[0].code == "WORKFLOW_RUN_BUSY"
    repository = SqlAlchemyWorkflowRunRepository(factory)
    run_id = saved[0].data["runId"]
    assert repository.get(run_id) == saved[0]
    assert repository.events(run_id, 0, 10)[0]["seq"] == 1
    repository.append(run_id, {"type": "cancelled"}, {"state": "cancelled"})
    assert repository.active_id() is None
    assert repository.create(_record()).data["state"] == "starting"
    factory.dispose()


def test_same_request_parallel_create_has_one_record_and_one_accepted_event(tmp_path):
    database = tmp_path / "workspace.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    original = _record()
    barrier = Barrier(2)

    def attempt(_index):
        repository = SqlAlchemyWorkflowRunRepository(factory)
        barrier.wait(timeout=3)
        return repository.create(deepcopy(original))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert results == [original, original]
    repository = SqlAlchemyWorkflowRunRepository(factory)
    assert len(repository.events(original.data["runId"], 0, 10)) == 1
    assert len(repository.list_runs(None, 0, 10)) == 1
    factory.dispose()
