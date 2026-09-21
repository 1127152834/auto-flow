from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from autoflow.application.project_runs.worker_capabilities import (
    ProjectWorkerCapabilities,
)
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunRow,
)
from tests.integration.test_project_capability_fencing import (
    capability_context,  # noqa: F401
)


@pytest.fixture
def rpc(capability_context):  # noqa: F811
    factory, _project, task, table, field, _record = capability_context
    visit = str(uuid4())
    request = {'nodeId': 'write', 'nodeVisitId': visit, 'attempt': 1,
               'commandId': project_command_id(task.run_id, 1, visit), 'operation': 'createRecord',
               'arguments': {'tableId': table['tableId'], 'datasetGeneration': table['datasetGeneration'],
                             'values': {field['ref']['fieldId']: 'created by worker'}}}
    # Security-boundary fixture: authorize one frozen node, then persist its visit.
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        prepared.execution_plan = {'nodes': [{'nodeId': 'write', 'moduleType': 'project_data', 'data': {'operation': 'createRecord'}}], 'orderedNodeIds': ['write']}
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({
            'eventId': str(uuid4()), 'runId': task.run_id, 'executionGeneration': 1,
            'nodeId': 'write', 'nodeVisitId': visit, 'attempt': 1, 'kind': 'nodeAttempt',
            'occurredAt': datetime.now(UTC).isoformat(), 'payload': {'status': 'started'},
        })
    return factory, task, request, ProjectWorkerCapabilities(factory)


@pytest.mark.asyncio
async def test_committed_command_replay_returns_original_record(rpc):
    factory, task, request, service = rpc
    first = await service.handle(task.run_id, 1, request)
    assert await service.handle(task.run_id, 1, request) == first
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DataRecordRow).where(DataRecordRow.values_json == request['arguments']['values'])) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation', ['generation', 'visit', 'command', 'node', 'operation', 'project'])
async def test_untrusted_worker_cannot_expand_authority(rpc, mutation):
    factory, task, request, service = rpc
    generation = 1
    if mutation == 'generation': generation = 2
    elif mutation == 'visit': request['nodeVisitId'] = str(uuid4())
    elif mutation == 'command': request['commandId'] = str(uuid4())
    elif mutation == 'node': request['nodeId'] = 'other'
    elif mutation == 'operation': request['operation'] = 'deleteRecord'
    elif mutation == 'project': request['arguments']['projectId'] = str(uuid4())
    with pytest.raises(ProjectError):
        await service.handle(task.run_id, generation, request)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DataRecordRow).where(DataRecordRow.values_json == request['arguments']['values'])) == 0


def test_previous_manual_checkpoint_remains_addressable_after_next_checkpoint(rpc):
    from autoflow.application.project_runs.manual_runtime import ProjectManualRuntime
    factory, task, request, _ = rpc
    identities = [str(uuid4()), str(uuid4())]
    with factory.begin() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        for identity in identities:
            repository.append_event({'eventId': str(uuid4()), 'runId': task.run_id, 'executionGeneration': 1, 'nodeId': request['nodeId'], 'nodeVisitId': request['nodeVisitId'], 'attempt': 1, 'kind': 'checkpoint', 'occurredAt': datetime.now(UTC), 'payload': {'manualItemId': identity}})
    runtime = ProjectManualRuntime(factory, None, None)
    first = runtime.checkpoint({'runId': task.run_id, 'manualItemId': identities[0]})
    assert first.payload['manualItemId'] == identities[0]


def test_field_preview_manifest_uses_existing_modify_field_permission(rpc):
    from types import SimpleNamespace

    from autoflow.application.project_runs.coordinator import _workflow_data_manifest
    from autoflow.domain.project_data.capabilities import TableCapabilityGrant
    from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
    from tests.fixtures.workflows import workflow_payload
    factory, _, request, _ = rpc
    table_id = request['arguments']['tableId']
    generation = request['arguments']['datasetGeneration']
    payload = workflow_payload()
    grant = {'tableId': table_id, 'datasetGeneration': generation, 'operations': ['modifyField'], 'fieldIds': [], 'readPurposes': []}
    payload['content']['nodes'] = [{'id': 'preview', 'type': 'project_data', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'project_data', 'operation': 'previewFieldChange', 'variableName': 'preview', 'arguments': {}, 'tableGrant': grant}}]
    payload['content']['edges'] = []
    with factory() as session:
        row = session.scalars(select(WorkflowDocumentRow)).first()
        row.document = payload
        manifest = _workflow_data_manifest(session, SimpleNamespace(workflow_id=row.id))
    assert manifest == {'tableGrants': [grant]}
    TableCapabilityGrant(table_id, generation, frozenset(grant['operations']), frozenset(), frozenset())


@pytest.mark.asyncio
@pytest.mark.parametrize('scope_state', ['valid', 'missing', 'wrong-definition', 'finished-call', 'cancelled-parent'])
async def test_child_capability_requires_live_frozen_parent_call(rpc, scope_state):
    from autoflow.infrastructure.database.workflow_runtime_models import (
        WorkflowRunEventRow,
    )
    factory, task, request, service = rpc
    call_visit = str(uuid4())
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        plan = prepared.execution_plan
        plan['document'] = {'nodes': [
            {'id': 'call', 'data': {'moduleType': 'subflow', 'subflowGroupId': 'child', 'inputs': {}, 'outputs': {}}},
            {'id': 'child', 'data': {'moduleType': 'subflow_header'}},
            {'id': 'write', 'data': {'moduleType': 'project_data'}},
        ], 'edges': [{'source': 'child', 'target': 'write'}]}
        prepared.execution_plan = dict(plan)
        # JSON mutation tracking needs an explicit dirty mark in this fixture.
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(prepared, 'execution_plan')
        scopes = [{'kind': 'subflow', 'id': 'wrong' if scope_state == 'wrong-definition' else 'child', 'callNodeId': 'call', 'callVisitId': call_visit}]
        event = session.scalar(select(WorkflowRunEventRow).where(WorkflowRunEventRow.node_visit_id == request['nodeVisitId']))
        event.payload = {'status': 'started', 'executionContext': {'scopes': [] if scope_state == 'missing' else scopes}}
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({
            'eventId': str(uuid4()), 'runId': task.run_id, 'executionGeneration': 1,
            'nodeId': 'call', 'nodeVisitId': call_visit, 'attempt': 1, 'kind': 'nodeAttempt',
            'occurredAt': datetime.now(UTC).isoformat(), 'payload': {'status': 'succeeded' if scope_state == 'finished-call' else 'started'},
        })
        if scope_state == 'cancelled-parent': run.status = 'cancelled'
    if scope_state == 'valid':
        assert (await service.handle(task.run_id, 1, request))['values'][0]['value'] == 'created by worker'
    else:
        with pytest.raises(ProjectError, match='执行能力请求'):
            await service.handle(task.run_id, 1, request)


@pytest.mark.asyncio
@pytest.mark.parametrize('scope_state', ['valid', 'missing', 'wrong-branch', 'wrong-join', 'finished-call', 'cancelled-parent'])
async def test_parallel_capability_requires_live_frozen_branch_owner(rpc, scope_state):
    from sqlalchemy.orm.attributes import flag_modified

    from autoflow.infrastructure.database.workflow_runtime_models import (
        WorkflowRunEventRow,
    )
    factory, task, request, service = rpc
    call_visit = str(uuid4())
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
        prepared.execution_plan['document'] = {'nodes': [
            {'id': 'fork', 'data': {'moduleType': 'set_variable', 'parallel': {'joinNodeId': 'join', 'outputs': {}}}},
            {'id': 'write', 'data': {'moduleType': 'project_data'}},
            {'id': 'other', 'data': {'moduleType': 'set_variable'}},
            {'id': 'join', 'data': {'moduleType': 'set_variable'}},
        ], 'edges': [{'source': source, 'target': target} for source, target in [('fork', 'write'), ('fork', 'other'), ('write', 'join'), ('other', 'join')]]}
        flag_modified(prepared, 'execution_plan')
        scope = {'kind': 'parallel', 'id': 'fork', 'callNodeId': 'fork', 'callVisitId': call_visit, 'branchNodeId': 'other' if scope_state == 'wrong-branch' else 'write', 'joinNodeId': 'wrong' if scope_state == 'wrong-join' else 'join'}
        event = session.scalar(select(WorkflowRunEventRow).where(WorkflowRunEventRow.node_visit_id == request['nodeVisitId']))
        event.payload = {'status': 'started', 'executionContext': {'scopes': [] if scope_state == 'missing' else [scope]}}
        SqlAlchemyWorkflowRuntimeRepository(session).append_event({
            'eventId': str(uuid4()), 'runId': task.run_id, 'executionGeneration': 1,
            'nodeId': 'fork', 'nodeVisitId': call_visit, 'attempt': 1, 'kind': 'nodeAttempt',
            'occurredAt': datetime.now(UTC).isoformat(), 'payload': {'status': 'succeeded' if scope_state == 'finished-call' else 'started'},
        })
        if scope_state == 'cancelled-parent': run.status = 'cancelled'
    if scope_state == 'valid':
        assert (await service.handle(task.run_id, 1, request))['values'][0]['value'] == 'created by worker'
    else:
        with pytest.raises(ProjectError, match='执行能力请求'):
            await service.handle(task.run_id, 1, request)
