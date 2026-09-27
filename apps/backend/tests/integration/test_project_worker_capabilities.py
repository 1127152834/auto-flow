"""Private worker admission against real migrated Task/Run facts."""

from datetime import UTC, datetime

import pytest

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.domain.project_runs.models import snapshot_to_dict
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_data_start import _setup, uid


@pytest.fixture
def worker_context(tmp_path):
    factory, project, automation, coordinator = _setup(
        tmp_path,
        resolve_status_input_ids=lambda automation: [
            item["inputId"] for item in automation.input_plan["inputs"]
        ],
        resolve_data_capability_manifest=lambda _session, automation: {
            "tableGrants": [
                {
                    "tableId": item["tableId"],
                    "datasetGeneration": item["datasetGeneration"],
                    "operations": ["readRecord", "updateRecord"],
                    "fieldIds": [
                        binding["fieldRef"]["fieldId"]
                        for binding in item["fieldBindings"]
                    ],
                    "readPurposes": ["workflow"],
                }
                for item in automation.input_plan["inputs"]
            ]
        },
    )
    from autoflow.application.project_data.catalog import DataCatalogService
    from autoflow.infrastructure.database.project_data_catalog import (
        SqlAlchemyProjectDataCatalog,
    )

    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    table_id = automation.input_plan['inputs'][0]['tableId']
    catalog.create_field(project, table_id, uid(), {
        'definition': {'key': 'unbound', 'name': '未授权列', 'type': 'string', 'required': False, 'validation': {}},
        'expectedTableRevision': catalog.fields(project, table_id)['tableRevision'],
        'sourceColumnPolicy': 'localOnly', 'existingRecordDefault': 'unbound-value-must-stay-private',
    })
    save_data_workflow(factory, automation)
    batch = coordinator.start(
        project,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project, batch.batch_id)[0]
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "running"
        run.execution_generation = 1
        run.capability_bindings = [
            {**item, "executionGeneration": 1} for item in run.capability_bindings
        ]
    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    request = {
        "nodeId": "data-node",
        "nodeVisitId": uid(),
        "attempt": 1,
        "commandId": uid(),
        "capability": "project.data.inputs",
        "arguments": {},
    }
    try:
        yield (
            factory,
            service,
            task,
            request,
            coordinator.get_snapshot(project, task.task_id),
        )
    finally:
        factory.dispose()


def commit_visit(factory, task, request, status="started"):
    with factory.begin() as session:
        SqlAlchemyWorkflowRuntimeRepository(session).append_event(
            {
                "eventId": uid(),
                "runId": task.run_id,
                "executionGeneration": 1,
                "kind": "nodeAttempt",
                "nodeId": request["nodeId"],
                "nodeVisitId": request["nodeVisitId"],
                "attempt": 1,
                "occurredAt": datetime.now(UTC).isoformat(),
                "payload": {"status": status},
            }
        )


def test_worker_requires_committed_active_visit_and_host_owned_identity(worker_context):
    factory, service, task, request, snapshot = worker_context
    with pytest.raises(ProjectError, match="visit"):
        service.worker_call(task.run_id, 1, request)
    commit_visit(factory, task, request)
    assert service.worker_call(task.run_id, 1, request) == {
        "inputs": snapshot_to_dict(snapshot)["inputs"]
    }
    for key in ("projectId", "taskId", "workspaceId", "executionGeneration"):
        with pytest.raises(ProjectError):
            service.worker_call(task.run_id, 1, {**request, key: uid()})
    commit_visit(factory, task, request, "succeeded")
    with pytest.raises(ProjectError, match="visit"):
        service.worker_call(task.run_id, 1, request)


def test_worker_cannot_use_old_generation_or_another_visit(worker_context):
    factory, service, task, request, _snapshot = worker_context
    commit_visit(factory, task, request)
    with pytest.raises(ProjectError):
        service.worker_call(task.run_id, 1, {**request, "nodeVisitId": uid()})
    with factory.begin() as session:
        session.get(WorkflowRunRow, task.run_id).execution_generation = 2
    with pytest.raises(ProjectError):
        service.worker_call(task.run_id, 1, request)


def test_worker_reads_writes_replays_and_preserves_cas(worker_context):
    factory, service, task, request, snapshot = worker_context
    commit_visit(factory, task, request)
    item = snapshot_to_dict(snapshot)["inputs"][0]
    ref = item["recordRef"]
    field_id = item["values"][0]["fieldId"]
    read = {
        **request,
        "nodeId": "read-node",
        "nodeVisitId": uid(),
        "capability": "project.data.read",
        "arguments": {
            "recordRef": ref,
            "fieldIds": [field_id],
            "readPurpose": "workflow",
        },
    }
    commit_visit(factory, task, read)
    before = service.worker_call(task.run_id, 1, read)["result"]
    write = {
        **request,
        "nodeId": "update-node",
        "nodeVisitId": uid(),
        "commandId": uid(),
        "capability": "project.data.update",
        "arguments": {
            "recordRef": ref,
            "changes": {field_id: "worker-written"},
            "expectedContentRevision": before["contentRevision"],
        },
    }
    commit_visit(factory, task, write)
    assert len(before['values']) == 1
    first = service.worker_call(task.run_id, 1, write)
    assert first["replayed"] is False
    assert "values" not in first["result"]
    replay = service.worker_call(task.run_id, 1, write)
    assert replay == {**first, "replayed": True}
    query = {
        **request,
        "nodeId": "operation-node",
        "nodeVisitId": uid(),
        "capability": "project.data.operation",
        "arguments": {"operationId": write["commandId"]},
    }
    commit_visit(factory, task, query)
    assert service.worker_call(task.run_id, 1, query) == {"operation": first["result"]}
    after = service.worker_call(task.run_id, 1, read)["result"]
    assert after["contentRevision"] == before["contentRevision"] + 1
    assert after["values"][0]["value"] == "worker-written"
    with pytest.raises(ProjectError):
        service.worker_call(task.run_id, 1, {**write, "commandId": uid()})
    with pytest.raises(ProjectError):
        service.worker_call(
            task.run_id,
            1,
            {
                **write,
                "arguments": {
                    **write["arguments"],
                    "changes": {field_id: "changed replay"},
                },
            },
        )
    assert service.worker_call(task.run_id, 1, read)["result"] == after
    for foreign in ({**ref, "projectId": uid()}, {**ref, "tableId": uid()}):
        with pytest.raises(ProjectError):
            service.worker_call(
                task.run_id,
                1,
                {**read, "arguments": {**read["arguments"], "recordRef": foreign}},
            )


def test_worker_cannot_select_another_workspace(worker_context, tmp_path):
    from autoflow.infrastructure.database.session import (
        create_session_factory,
        migrate_database,
    )

    _factory, _service, task, request, _snapshot = worker_context
    path = tmp_path / "other-workspace.sqlite3"
    migrate_database(path)
    other = create_session_factory(path)
    try:
        with pytest.raises(ProjectError, match="no project task"):
            ProjectDataCapabilityService(
                SqlAlchemyProjectDataCapabilities(other)
            ).worker_call(task.run_id, 1, request)
    finally:
        other.dispose()


def save_data_workflow(factory, automation):
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
    from tests.fixtures.workflows import workflow_payload

    source = automation.input_plan["inputs"][0]
    field_id = source["fieldBindings"][0]["fieldRef"]["fieldId"]
    binding = {
        "tableId": source["tableId"],
        "datasetGeneration": source["datasetGeneration"],
        "fieldIds": [field_id],
    }
    import json

    ref = "{snapshot['inputs'][0]['recordRef']}"

    def argument_text(arguments):
        text = json.dumps(arguments)
        for expression in (ref, "{record['result']['contentRevision']}"):
            text = text.replace(json.dumps(expression), expression)
        return text

    steps = [
        ("data-node", {"action": "inputs", "resultVariable": "snapshot"}),
        (
            "read-node",
            {
                "action": "read",
                "binding": binding,
                "resultVariable": "record",
                "arguments": argument_text(
                    {
                        "recordRef": ref,
                        "fieldIds": [field_id],
                        "readPurpose": "workflow",
                    }
                ),
            },
        ),
        (
            "operation-node",
            {
                "action": "operation",
                "resultVariable": "prior",
                "arguments": {"operationId": "00000000-0000-4000-8000-000000000000"},
            },
        ),
        (
            "update-node",
            {
                "action": "update",
                "binding": binding,
                "resultVariable": "written",
                "arguments": argument_text(
                    {
                        "recordRef": ref,
                        "changes": {field_id: "production-worker-written"},
                        "expectedContentRevision": "{record['result']['contentRevision']}",
                    }
                ),
            },
        ),
    ]
    document = workflow_payload(automation.workflow_id)["content"]
    document.update(
        {
            "id": automation.workflow_id,
            "schemaVersion": 3,
            "nodes": [
                {
                    "id": node_id,
                    "type": "project_data",
                    "position": {"x": index * 160, "y": 0},
                    "data": {"moduleType": "project_data", "config": config},
                }
                for index, (node_id, config) in enumerate(steps)
            ],
            "edges": [
                {
                    "id": str(index),
                    "source": steps[index][0],
                    "target": steps[index + 1][0],
                }
                for index in range(len(steps) - 1)
            ],
        }
    )
    WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
        automation.workflow_id,
        document,
        expected_revision=1,
        client_request_id=uid(),
    )


@pytest.mark.asyncio
async def test_production_worker_uses_frozen_grants_and_writes_real_sqlite(tmp_path):
    from autoflow.infrastructure.database.project_data_models import DataRecordRow
    from autoflow.infrastructure.database.project_run_models import (
        ProjectTaskInputSnapshotRow,
    )
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    from tests.integration.test_project_data_worker import (
        _dispatcher,
        _NoBrowserResources,
    )

    factory, project, automation, coordinator = _setup(tmp_path)
    worker = ProjectWorkflowWorkerManager(
        tmp_path / "capability-worker",
        start_timeout=10,
        project_data=ProjectDataCapabilityService(
            SqlAlchemyProjectDataCapabilities(factory)
        ),
    )
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        save_data_workflow(factory, automation)
        batch = coordinator.start(
            project,
            automation.automation_id,
            uid(),
            {
                "expectedAutomationRevision": automation.management_revision,
                "parameters": {},
                "maxTasks": 1,
                "concurrency": 1,
            },
        )[0]
        assert (
            ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id)
            == "ready"
        )
        task = coordinator.list_tasks(project, batch.batch_id)[0]
        with factory() as session:
            run = SqlAlchemyWorkflowRuntimeRepository(session).get_run(
                run_id=task.run_id
            )
            inputs = session.get(
                ProjectTaskInputSnapshotRow, task.input_snapshot_id
            ).inputs
        await dispatcher.dispatch(
            run.run_id,
            expected_status_revision=run.status_revision,
            execution_generation=run.execution_generation,
        )
        await dispatcher.wait_idle()
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            finished = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
            assert finished.status == "succeeded", [
                (event.kind, event.payload) for event in events
            ]
            succeeded = [
                event.node_id
                for event in events
                if event.kind == "nodeAttempt"
                and event.payload.get("status") == "succeeded"
            ]
            assert succeeded == [
                "data-node",
                "read-node",
                "operation-node",
                "update-node",
            ]
            ref = inputs[0]["recordRef"]
            row = session.get(
                DataRecordRow,
                (
                    ref["datasetGeneration"],
                    ref["recordKey"]["type"],
                    ref["recordKey"]["value"],
                ),
            )
            assert row.content_revision == inputs[0]["contentRevision"] + 1
            assert "production-worker-written" in row.values_json.values()
            assert (
                session.get(ProjectTaskInputSnapshotRow, task.input_snapshot_id).inputs
                == inputs
            )
        assert not worker.busy()
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_studio_rejects_task_capability_before_acquiring_resources(tmp_path):
    from autoflow.adapters.events.workflows import StudioEventJournal
    from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.application.workflows.executors.production import (
        build_production_executor_registry,
    )
    from autoflow.application.workflows.runs import WorkflowRunService
    from autoflow.application.workflows.runtime import WorkflowRuntime
    from autoflow.domain.workflows.runs import WorkflowRunError
    from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
    from tests.unit.workflows.test_run_coordinator import (
        FakeProfiles,
        FakeResources,
        FakeWorkers,
        _none,
        _profile,
    )

    factory, _project, automation, _coordinator = _setup(tmp_path)
    workers, resources = FakeWorkers(), FakeResources()
    repository = SqlAlchemyWorkflowRuns(factory)
    coordinator = WorkflowRunCoordinator(
        documents=WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)),
        runs=WorkflowRunService(repository), run_repository=repository,
        runtime=WorkflowRuntime(build_production_executor_registry()),
        profiles=FakeProfiles(_profile()), installed_kernels=list,
        resolve_proxy=lambda _profile, _run_id: _none(), read_license=lambda: None,
        workers=workers, resources=resources, events=StudioEventJournal(), artifact_root=tmp_path / 'workspace',
    )
    try:
        save_data_workflow(factory, automation)
        with pytest.raises(WorkflowRunError, match='项目自动化任务') as error:
            await coordinator.start(automation.workflow_id, {'runId': uid(), 'documentId': automation.workflow_id, 'profileId': 'profile-1'})
        assert error.value.code == 'CAPABILITY_MISSING'
        assert workers.payloads == [] and resources.acquired == []
    finally:
        factory.dispose()
