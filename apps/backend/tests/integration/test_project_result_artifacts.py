"""Real SQLite/HTTP result artifacts; worker ACK transport is a controlled seam."""

import base64
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunArtifactRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from tests.contract.test_project_run_evidence import NOW, add_artifact, prepared
from tests.integration.test_project_run_dispatch import services

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aQ1sAAAAASUVORK5CYII="
)


def result_event(run_id, root, *, generation=0):
    artifact_id = str(uuid4())
    relative = f"runs/{run_id}/generation-{generation}/{artifact_id}.png"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG)
    return {
        "eventId": str(uuid4()),
        "runId": run_id,
        "executionGeneration": generation,
        "kind": "artifact",
        "nodeId": "open",
        "nodeVisitId": "result-visit",
        "attempt": 1,
        "occurredAt": NOW.isoformat(),
        "payload": {
            "artifactId": artifact_id,
            "kind": "screenshot",
            "purpose": "result",
            "availability": "available",
            "relativePath": relative,
            "mediaType": "image/png",
            "byteSize": len(PNG),
            "sha256": sha256(PNG).hexdigest(),
            "unavailableReason": None,
        },
    }, path


def artifact_counts(factory, run_id):
    with factory() as session:
        return (
            session.get(WorkflowRunRow, run_id).last_sequence,
            session.scalar(
                select(func.count())
                .select_from(WorkflowRunEventRow)
                .where(WorkflowRunEventRow.run_id == run_id)
            ),
            session.scalar(
                select(func.count())
                .select_from(WorkflowRunArtifactRow)
                .where(WorkflowRunArtifactRow.run_id == run_id)
            ),
        )


def test_result_event_and_artifact_index_commit_rollback_and_replay_are_atomic(
    tmp_path,
):
    client, _, factory, _, task = prepared(tmp_path)
    try:
        event, path = result_event(task.run_id, tmp_path / "workspace")
        before = artifact_counts(factory, task.run_id)
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            repository.append_event(event)
            assert (
                repository.get_artifact(
                    task.run_id, event["payload"]["artifactId"]
                ).purpose
                == "result"
            )
            session.rollback()
        assert artifact_counts(factory, task.run_id) == before
        with factory.begin() as session:
            committed = SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
        after = (before[0] + 1, before[1] + 1, before[2] + 1)
        assert artifact_counts(factory, task.run_id) == after
        with factory.begin() as session:
            replayed = SqlAlchemyWorkflowRuntimeRepository(session).append_event(
                deepcopy(event)
            )
            assert replayed.sequence == committed.sequence
        assert artifact_counts(factory, task.run_id) == after
        changed = deepcopy(event)
        changed["payload"]["sha256"] = "0" * 64
        with (
            pytest.raises(WorkflowRuntimeError) as conflict,
            factory.begin() as session,
        ):
            SqlAlchemyWorkflowRuntimeRepository(session).append_event(changed)
        assert conflict.value.code == "RUN_EVENT_CONFLICT"
        assert artifact_counts(factory, task.run_id) == after
        assert path.read_bytes() == PNG
    finally:
        client.close()
        factory.dispose()


def test_result_and_error_screenshots_share_project_scoped_list_detail_and_download(
    tmp_path,
):
    client, _, factory, project, task = prepared(tmp_path)
    try:
        event, path = result_event(task.run_id, tmp_path / "workspace")
        artifact_id = event["payload"]["artifactId"]
        with factory.begin() as session:
            SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
        error_id, _ = add_artifact(factory, task, tmp_path / "workspace")
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            artifact = repository.get_artifact(task.run_id, artifact_id)
            assert artifact is not None and artifact.purpose == "result"
            items, total = repository.list_artifacts(task.run_id, offset=0, limit=1)
            assert total == 2 and [item.artifact_id for item in items] == [artifact_id]
            items, total = repository.list_artifacts(task.run_id, offset=1, limit=1)
            assert total == 2 and [item.artifact_id for item in items] == [error_id]
        prefix = f"/api/v1/projects/{project.project_id}/tasks/{task.task_id}/artifacts"
        page = client.get(prefix, params={"pageSize": 1})
        assert page.status_code == 200, page.text
        assert page.json()["total"] == 2
        result = page.json()["items"][0]
        assert result["artifactId"] == artifact_id and result["purpose"] == "result"
        assert result["eventSequence"] == 6 and result["executionGeneration"] == 0
        assert result["nodeVisitId"] == "result-visit"
        assert (
            result["byteSize"] == len(PNG)
            and result["sha256"] == sha256(PNG).hexdigest()
        )
        assert "relativePath" not in result and str(path) not in page.text
        detail = client.get(f"{prefix}/{artifact_id}")
        assert detail.status_code == 200 and detail.json() == result
        image = client.get(result["contentUrl"])
        assert image.status_code == 200 and image.headers["content-type"] == "image/png"
        assert image.content == PNG
        for suffix in ("", f"/{artifact_id}", f"/{artifact_id}/content"):
            foreign = client.get(
                f"/api/v1/projects/{uuid4()}/tasks/{task.task_id}/artifacts{suffix}"
            )
            assert foreign.status_code == 404
        path.write_bytes(b"damaged")
        damaged = client.get(result["contentUrl"])
        assert damaged.status_code == 409
        assert damaged.json()["error"]["code"] == "RUN_ARTIFACT_UNAVAILABLE"
    finally:
        client.close()
        factory.dispose()


def test_committed_result_with_unknown_ack_is_not_discarded_but_uncommitted_result_is(
    tmp_path,
):
    factory, coordinator, project, batch, worker, core, _, _ = services(tmp_path)
    try:
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = core.query_run(task.run_id)
        event, path = result_event(run.run_id, tmp_path / "workspace")
        with factory.begin() as session:
            SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
        # ACK uncertainty is represented by invoking the actual parent cleanup gate
        # after SQL commit; no mock replaces its database lookup or persisted facts.
        core._discard_uncommitted_artifact(run, event)
        assert worker.discarded == []
        assert path.read_bytes() == PNG
        with factory() as session:
            assert (
                SqlAlchemyWorkflowRuntimeRepository(session).get_artifact(
                    run.run_id, event["payload"]["artifactId"]
                )
                is not None
            )
        missing, uncommitted_path = result_event(run.run_id, tmp_path / "workspace")
        core._discard_uncommitted_artifact(run, missing)
        assert worker.discarded == [
            (
                run.run_id,
                run.execution_generation,
                missing["payload"]["artifactId"],
                missing["payload"]["relativePath"],
            )
        ]
        # Synthetic worker only records the exact authorized deletion request.
        assert uncommitted_path.exists() and path.read_bytes() == PNG
    finally:
        factory.dispose()


def test_uncommitted_artifact_identity_cannot_discard_another_registered_result_path(
    tmp_path,
):
    factory, coordinator, project, batch, worker, core, _, _ = services(tmp_path)
    try:
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = core.query_run(task.run_id)
        event, path = result_event(run.run_id, tmp_path / "workspace")
        with factory.begin() as session:
            SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
        alias = deepcopy(event)
        alias["eventId"] = str(uuid4())
        alias["payload"]["artifactId"] = str(uuid4())
        assert alias["payload"]["relativePath"] == event["payload"]["relativePath"]
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            assert (
                repository.get_artifact(run.run_id, alias["payload"]["artifactId"])
                is None
            )
            assert repository.artifact_path_is_registered(
                run.run_id, alias["payload"]["relativePath"]
            )
        before = artifact_counts(factory, run.run_id)
        core._discard_uncommitted_artifact(run, alias)
        assert worker.discarded == []
        assert path.read_bytes() == PNG
        assert artifact_counts(factory, run.run_id) == before
        with factory() as session:
            kept = SqlAlchemyWorkflowRuntimeRepository(session).get_artifact(
                run.run_id, event["payload"]["artifactId"]
            )
            assert kept is not None and kept.purpose == "result"
    finally:
        factory.dispose()
