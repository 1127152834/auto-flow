"""Real project task over a loopback SSH/SFTP server, without a browser."""

from __future__ import annotations

import asyncio
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pytest

from autoflow.application.project_runs.evidence import ProjectRunEvidence
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.domain.workflows.catalog import runnable_module_types
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflows import (
    SqlAlchemyWorkflowDocuments,
    SqlAlchemyWorkflowRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_b6_ssh_worker import _LocalSSHServer
from tests.integration.test_project_data_worker import (
    _dispatcher,
    _NoBrowserResources,
    _studio_payload,
)
from tests.integration.test_project_run_start import setup, start_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["success", "empty", "failure", "stop"])
async def test_project_task_runs_five_ssh_nodes_and_persists_download(
    tmp_path: Path, scenario: str,
) -> None:
    server = _LocalSSHServer(tmp_path / "remote-host")
    server.start()
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    upload = tmp_path / "upload.bin"
    download = tmp_path / "download.bin"
    upload.write_bytes(b"" if scenario == "empty" else b"project-ssh-roundtrip")
    types = (
        "ssh_connect", "ssh_execute_command", "ssh_upload_file",
        "ssh_download_file", "ssh_disconnect",
    )
    assert set(types) <= runnable_module_types()
    configs = (
        {"connectionName": "fixture", "host": "127.0.0.1", "port": server.port,
         "username": "tester", "password": "{{cred:SSH测试.password}}", "timeout": 5},
        {"connectionName": "fixture", "command": {"failure": "unsupported", "stop": "wait"}.get(scenario, "printf ok"), "outputVariable": "ssh_result"},
        {"connectionName": "fixture", "localPath": str(upload), "remotePath": "/remote/roundtrip.bin"},
        {"connectionName": "fixture", "remotePath": "/remote/roundtrip.bin", "localPath": str(download)},
        {"connectionName": "fixture"},
    )
    document = _studio_payload(automation.workflow_id)
    document.update(
        schemaVersion=3,
        nodes=[{"id": f"ssh-{index}", "type": kind, "position": {"x": index * 160, "y": 0},
                "data": {"moduleType": kind, "config": config}}
               for index, (kind, config) in enumerate(zip(types, configs, strict=True))],
        edges=[{"id": f"edge-{index}", "source": f"ssh-{index}", "target": f"ssh-{index + 1}"}
               for index in range(4)],
        variables=[],
    )
    WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
        automation.workflow_id, document, expected_revision=1,
        client_request_id=str(uuid4()),
    )
    runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
    coordinator._core = runtime
    worker = ProjectWorkflowWorkerManager(
        tmp_path / "ssh-project-worker",
        resolve_credential=lambda name: {"password": "secret"} if name == "SSH测试" else {},
    )
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        batch, _, _ = coordinator.start(
            project.project_id, automation.automation_id, str(uuid4()), start_payload(automation),
        )
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert run is not None
        running = await dispatcher.dispatch(
            run.run_id, expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        if scenario == "stop":
            assert await asyncio.to_thread(server.command_started.wait, 15)
            started = monotonic()
            await dispatcher.cancel(
                run.run_id, expected_status_revision=running.status_revision,
                execution_generation=running.execution_generation,
            )
        await dispatcher.wait_idle()
        if scenario == "stop":
            assert monotonic() - started < 3
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        expected_status = {"failure": "failed", "stop": "cancelled"}.get(scenario, "succeeded")
        assert finished is not None and finished.status == expected_status, (
            finished.error if finished else None,
            [(event.kind, event.node_id, dict(event.payload)) for event in events],
        )
        assert "secret" not in str(events)
        assert not resources.requests and not worker.busy()
        for _ in range(100):
            if all(not transport.is_active() for transport in server.transports) and all(
                command.poll() is not None for command in server.commands
            ):
                break
            await asyncio.sleep(0.02)
        assert all(not transport.is_active() for transport in server.transports)
        assert all(command.poll() is not None for command in server.commands)
        evidence = ProjectRunEvidence(factory, tmp_path / "workspace")
        artifacts, total = evidence.artifacts(project.project_id, task.task_id)
        if scenario in {"failure", "stop"}:
            assert not download.exists()
            assert not (tmp_path / "remote-host/remote/roundtrip.bin").exists()
            if scenario == "failure":
                assert total == 1
                assert artifacts[0].kind == "screenshot"
                assert artifacts[0].availability == "unavailable"
                assert artifacts[0].unavailable_reason == "SCREENSHOT_PAGE_UNAVAILABLE"
            else:
                assert total == 0 and artifacts == []
            assert not any(event.node_id in {"ssh-2", "ssh-3", "ssh-4"} for event in events)
            if scenario == "failure":
                assert any(event.node_id == "ssh-1" and event.payload.get("status") == "failed" for event in events)
            return
        assert (tmp_path / "remote-host/remote/roundtrip.bin").read_bytes() == upload.read_bytes()
        assert download.read_bytes() == upload.read_bytes()
        assert [event.node_id for event in events if event.kind == "nodeAttempt" and event.payload.get("status") == "succeeded"] == [f"ssh-{index}" for index in range(5)]
        assert any(event.kind == "output" and event.payload.get("value") == "ok\n" for event in events)
        assert total == 1 and artifacts[0].kind == "file"
        assert evidence.artifact_content(project.project_id, task.task_id, artifacts[0].artifact_id)[0] == upload.read_bytes()
        assert "secret" not in str(events)
        assert not resources.requests and not worker.busy()
        assert all(not transport.is_active() for transport in server.transports)
    finally:
        await dispatcher.shutdown()
        factory.dispose()
        server.close()
