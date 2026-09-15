from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest

from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from tests.integration.test_project_run_start import setup, start_payload

NOW = datetime(2026, 9, 15, tzinfo=UTC)


def prepared(tmp_path):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    batch, _, _ = coordinator.start(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        start_payload(automation),
    )
    return factory, coordinator.list_tasks(project.project_id, batch.batch_id)[0]


def artifact_event(task, *, relative_path=None):
    artifact_id = str(uuid4())
    content = b"png"
    return {
        "eventId": str(uuid4()),
        "runId": task.run_id,
        "executionGeneration": 0,
        "kind": "artifact",
        "nodeId": "open",
        "nodeVisitId": "visit-1",
        "attempt": 1,
        "occurredAt": NOW.isoformat(),
        "payload": {
            "artifactId": artifact_id,
            "kind": "screenshot",
            "purpose": "error",
            "availability": "available",
            "relativePath": relative_path
            or f"runs/{task.run_id}/generation-0/{artifact_id}.png",
            "mediaType": "image/png",
            "byteSize": len(content),
            "sha256": sha256(content).hexdigest(),
            "unavailableReason": None,
            "createdAt": NOW.isoformat(),
        },
    }


def test_artifact_event_and_index_are_committed_once(tmp_path):
    factory, task = prepared(tmp_path)
    value = artifact_event(task)
    with factory.begin() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        first = repository.append_event(value)
        replay = repository.append_event(value)
        artifacts, total = repository.list_artifacts(task.run_id, offset=0, limit=20)

    assert replay == first
    assert total == 1
    assert [item.artifact_id for item in artifacts] == [
        value["payload"]["artifactId"]
    ]
    factory.dispose()


def test_escape_metadata_is_rejected_without_advancing_run_sequence(tmp_path):
    factory, task = prepared(tmp_path)
    with factory() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        with pytest.raises(WorkflowRuntimeError) as caught:
            repository.append_event(artifact_event(task, relative_path="../secret.png"))
        session.rollback()

    with factory() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        assert repository.get_run(run_id=task.run_id).last_sequence == 0
        assert repository.list_artifacts(task.run_id, offset=0, limit=20) == ([], 0)
    assert caught.value.code == "RUN_ARTIFACT_INVALID"
    factory.dispose()
