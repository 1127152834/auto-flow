from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from threading import Barrier

from sqlalchemy import inspect

from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload


def test_documents_survive_reopen_and_are_isolated_by_workspace(tmp_path):
    first, second = tmp_path / "a.sqlite3", tmp_path / "b.sqlite3"
    payload = workflow_payload()
    migrate_database(first)
    factory = create_session_factory(first)
    repository = SqlAlchemyWorkflowRepository(factory)
    saved = WorkflowService(repository).create(**payload)
    assert "workflow_documents" in inspect(factory.kw["bind"]).get_table_names()
    factory.dispose()
    migrate_database(first)
    reopened = create_session_factory(first)
    assert SqlAlchemyWorkflowRepository(reopened).get(saved.document["id"]) == saved
    migrate_database(second)
    other = create_session_factory(second)
    assert SqlAlchemyWorkflowRepository(other).list() == []
    reopened.dispose()
    other.dispose()


def test_competing_saves_have_one_winner_and_do_not_overwrite_each_other(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    service = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    payload = workflow_payload()
    service.create(**payload)
    barrier = Barrier(2)

    def save(name):
        document = deepcopy(payload["document"])
        document["name"] = name
        barrier.wait(timeout=5)
        try:
            return service.save(document["id"], document, payload["layout"], 1)
        except WorkflowError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["first", "second"]))
    successes = [result for result in results if not isinstance(result, WorkflowError)]
    failures = [result for result in results if isinstance(result, WorkflowError)]
    assert len(successes) == len(failures) == 1
    assert failures[0].code == "WORKFLOW_REVISION_CONFLICT"
    assert service.get(payload["document"]["id"]) == successes[0]
    assert successes[0].revision == 2
    factory.dispose()


def test_same_id_concurrent_create_is_idempotent_and_list_orders_latest_first(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    service = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    payload = workflow_payload()
    barrier = Barrier(2)

    def create(_):
        barrier.wait(timeout=5)
        return service.create(**deepcopy(payload))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, range(2)))
    assert results[0] == results[1]
    other = workflow_payload("d45f286f-129d-4e3b-a09b-995c3b491610")
    service.create(**other)
    assert service.list()[0].document["id"] == other["document"]["id"]
    updated = deepcopy(payload["document"])
    updated["name"] = "recent"
    service.save(updated["id"], updated, payload["layout"], 1)
    assert service.list()[0].document["id"] == updated["id"]
    assert service.list()[0].updated_at <= datetime.now(UTC)
    factory.dispose()
