from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from threading import Event

import pytest

from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
from autoflow.application.workflows.credentials import StudioCredentialService
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.studio_credentials import (
    SqlAlchemyStudioCredentials,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager
from tests.fixtures.model_management import FakeCredentialStore
from tests.unit.workflows.test_run_coordinator import (
    FakeProfiles,
    FakeResources,
    _none,
    _profile,
)


def harness(tmp_path, resolver_override=None):
    database = tmp_path / "run.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    credentials = StudioCredentialService(
        SqlAlchemyStudioCredentials(sessions), FakeCredentialStore()
    )
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(sessions))
    documents.create(
        {
            "id": "flow",
            "name": "credential pipe",
            "nodes": [
                {
                    "id": "assert",
                    "data": {
                        "moduleType": "assert_checkpoint",
                        "config": {
                            "checkType": "variable",
                            "actualValue": "{{凭据:账号.password}}",
                            "expectedValue": "{{cred:账号.password}}",
                            "operator": "==",
                            "onFail": "stop",
                        },
                    },
                },
            ],
            "edges": [],
            "variables": [],
        },
        client_request_id="save",
    )
    repository = SqlAlchemyWorkflowRuns(sessions)
    runs = WorkflowRunService(repository)
    events = []

    async def on_event(event):
        if event.get("type") != "credential:read":
            events.append(event)
        await coordinator.on_worker_event(event)

    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        termination_timeout=0.5,
        on_event=on_event,
        on_exit=lambda run_id, code: coordinator.on_worker_exit(run_id, code),
    )
    coordinator = WorkflowRunCoordinator(
        documents=documents,
        runs=runs,
        run_repository=repository,
        runtime=WorkflowRuntime(build_production_executor_registry()),
        profiles=FakeProfiles(_profile()),
        installed_kernels=list,
        resolve_proxy=lambda _p, _r: _none(),
        read_license=lambda: None,
        workers=manager,
        resources=FakeResources(),
        events=StudioEventJournal(),
        artifact_root=tmp_path / "artifacts",
        resolve_credential=resolver_override or credentials.resolve,
    )
    return coordinator, manager, runs, credentials, events, database


@pytest.mark.asyncio
@pytest.mark.parametrize("secret", ["private-unique-credential-value", ""])
@pytest.mark.parametrize("nested", [False, True])
async def test_real_worker_resolves_credentials_and_never_persists_secret(
    tmp_path, secret, nested
):
    coordinator, manager, runs, credentials, events, database = harness(tmp_path)
    credentials.upsert("账号", {"password": secret}, None)
    target = "flow"
    if nested:
        target = "parent"
        coordinator._documents.create(
            {
                "id": target,
                "name": "parent",
                "nodes": [
                    {
                        "id": "nested",
                        "data": {
                            "moduleType": "run_workflow_file",
                            "config": {"workflowFile": "flow", "waitComplete": True},
                        },
                    }
                ],
                "edges": [],
                "variables": [],
            },
            client_request_id="parent-save",
        )
    try:
        await coordinator.start(
            target, {"runId": "run", "documentId": target, "profileId": "profile-1"}
        )
        async with asyncio.timeout(15):
            while manager.busy():
                await asyncio.sleep(0.02)
        assert runs.get("run").status == "completed"
        assert runs.get("run").cleanup_state == "completed"
        assert manager.active_processes() == []
        assert any(
            e.get("type") == "execution:node_complete" and e.get("success")
            for e in events
        )
        assert all(e.get("type") != "credential:result" for e in events)
        public = json.dumps(
            [asdict(runs.get("run")), runs.events("run"), events],
            default=str,
            ensure_ascii=False,
        )
        assert "credential:read" not in public
        if secret:
            assert secret not in public
            assert secret.encode() not in database.read_bytes()
            for file in (tmp_path / "artifacts").rglob("*"):
                if file.is_file():
                    assert secret.encode() not in file.read_bytes()
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["账号.password", "账号.", ".password"])
async def test_missing_credential_preserves_original_placeholder_failure(
    tmp_path, reference
):
    coordinator, manager, runs, _credentials, _events, _database = harness(tmp_path)
    document = coordinator._documents.get("flow")
    payload = dict(document.document)
    payload["nodes"][0]["data"]["config"].update(
        actualValue="{{凭据:" + reference + "}}",
        expectedValue="{{cred:" + reference + "}}",
    )
    coordinator._documents.update(
        "flow",
        payload,
        expected_revision=document.revision,
        client_request_id="missing-ref",
    )
    try:
        await coordinator.start(
            "flow", {"runId": "missing", "documentId": "flow", "profileId": "profile-1"}
        )
        async with asyncio.timeout(15):
            while manager.busy():
                await asyncio.sleep(0.02)
        assert runs.get("missing").status == "failed"
        assert any(
            e.get("type") == "execution:node_complete" and e.get("success") is False
            for e in _events
        )
        assert runs.get("missing").cleanup_state == "completed"
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_native_store_wait_cannot_block_stop_or_send_late_secret(tmp_path):
    entered, release = Event(), Event()

    def blocked(_name):
        entered.set()
        release.wait(10)
        return {"password": "late-secret-must-not-be-sent"}

    coordinator, manager, runs, _credentials, _events, _database = harness(
        tmp_path, blocked
    )
    commands = []
    original_send = manager.send_command

    async def record(run_id, command):
        commands.append(command.copy())
        await original_send(run_id, command)

    manager.send_command = record
    try:
        await coordinator.start(
            "flow", {"runId": "blocked", "documentId": "flow", "profileId": "profile-1"}
        )
        async with asyncio.timeout(10):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        async with asyncio.timeout(2):
            await coordinator.stop("flow", "blocked")
        assert not release.is_set()
        assert runs.get("blocked").status == "stopped"
        assert runs.get("blocked").cleanup_state == "completed"
        assert manager.active_processes() == []
        release.set()
        await asyncio.sleep(0.05)
        assert commands == []
    finally:
        release.set()
        await manager.shutdown()
