from copy import deepcopy
from uuid import uuid4

import pytest

from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload


def services(tmp_path):
    database = tmp_path / "content-uow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    workflows = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    workflow = workflows.create(workflow_payload(), str(uuid4()))
    runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
    return factory, workflow, runtime


def prepare(runtime, workflow, *, operation_id=None, revision=None, uow=None):
    return runtime.prepare_content(
        prepare_operation_id=operation_id or str(uuid4()),
        workflow_id=workflow.workflow_id,
        source_revision=workflow.revision if revision is None else revision,
        available_capabilities=["browser.cloakbrowser"],
        uow=uow,
    )


def prepare_run(runtime, content, uow):
    return runtime.prepare_run(
        run_request_id=str(uuid4()),
        prepared_content_id=content.prepared_content_id,
        parameters={"enabled": False, "count": 0},
        input_snapshot_ref=None,
        resource_request={"browser": "none"},
        capability_bindings=[],
        uow=uow,
    )


def test_content_and_queued_run_roll_back_with_the_callers_uow(tmp_path):
    factory, workflow, runtime = services(tmp_path)
    with factory() as session:
        content = prepare(runtime, workflow, uow=session)
        run = prepare_run(runtime, content, session)
        session.flush()
        session.rollback()

    assert (
        runtime.query_prepared_content(prepared_content_id=content.prepared_content_id)
        is None
    )
    assert runtime.query_run(run_id=run.run_id) is None
    factory.dispose()


def test_content_and_queued_run_commit_together_in_the_callers_uow(tmp_path):
    factory, workflow, runtime = services(tmp_path)
    with factory() as session:
        content = prepare(runtime, workflow, uow=session)
        run = prepare_run(runtime, content, session)
        session.commit()

    assert (
        runtime.query_prepared_content(prepared_content_id=content.prepared_content_id)
        == content
    )
    assert runtime.query_run(run_id=run.run_id) == run
    factory.dispose()


def test_prepare_content_reads_the_current_workflow_revision_from_the_same_uow(
    tmp_path,
):
    factory, workflow, runtime = services(tmp_path)
    with factory() as session:
        row = session.get(WorkflowDocumentRow, workflow.workflow_id)
        assert row is not None
        row.revision = workflow.revision + 1
        row.document = deepcopy(row.document)
        row.document["content"]["name"] = "同事务中的新版"
        session.flush()

        content = prepare(runtime, workflow, revision=row.revision, uow=session)
        assert content.source_revision == row.revision
        assert content.document["content"]["name"] == "同事务中的新版"
        session.rollback()

    assert (
        runtime.query_prepared_content(prepared_content_id=content.prepared_content_id)
        is None
    )
    factory.dispose()


@pytest.mark.parametrize("revision", [0, 2])
def test_prepare_content_rejects_old_and_future_revisions_inside_uow(
    tmp_path, revision
):
    factory, workflow, runtime = services(tmp_path)
    with factory() as session, pytest.raises(WorkflowRuntimeError) as error:
        prepare(runtime, workflow, revision=revision, uow=session)
    assert error.value.code == "WORKFLOW_REVISION_CONFLICT"
    factory.dispose()


def test_same_prepare_operation_id_rejects_a_different_request_in_one_uow(tmp_path):
    factory, workflow, runtime = services(tmp_path)
    operation_id = str(uuid4())
    with factory() as session:
        prepare(runtime, workflow, operation_id=operation_id, uow=session)
        with pytest.raises(WorkflowRuntimeError) as error:
            runtime.prepare_content(
                prepare_operation_id=operation_id,
                workflow_id=workflow.workflow_id,
                source_revision=workflow.revision,
                available_capabilities=["browser.cloakbrowser", "different.capability"],
                uow=session,
            )
        assert error.value.code == "OPERATION_PAYLOAD_MISMATCH"
        session.rollback()
    factory.dispose()


def test_legacy_prepare_content_without_uow_still_commits_and_is_queryable(tmp_path):
    factory, workflow, runtime = services(tmp_path)

    content = runtime.prepare_content(
        prepare_operation_id=str(uuid4()),
        workflow_id=workflow.workflow_id,
        source_revision=workflow.revision,
        available_capabilities=["browser.cloakbrowser"],
    )

    assert (
        runtime.query_prepared_content(prepared_content_id=content.prepared_content_id)
        == content
    )
    factory.dispose()
