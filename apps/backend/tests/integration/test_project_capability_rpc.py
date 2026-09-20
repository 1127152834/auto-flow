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
