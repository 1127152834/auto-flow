"""Route worker requests through authoritative Task/Run capability facts."""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import Any

from sqlalchemy import select

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.domain.project_data import capabilities as commands
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)

DATA_COMMANDS = {
    'readRecord': ('read_record', commands.ReadProjectRecordRequest),
    'queryRecords': ('query_records', commands.QueryProjectRecordsRequest),
    'createRecord': ('create_record', commands.CreateProjectRecordCommand),
    'updateRecord': ('update_record', commands.UpdateProjectRecordCommand),
    'deleteRecord': ('delete_record', commands.DeleteProjectRecordCommand),
    'setRecordStatus': ('set_record_status', commands.SetRecordStatusCommand),
    'addField': ('add_field', commands.AddProjectFieldCommand),
    'ensureField': ('ensure_field', commands.EnsureProjectFieldCommand),
    'modifyField': ('modify_field', commands.ModifyProjectFieldCommand),
    'previewFieldChange': ('preview_field_change', commands.PreviewProjectFieldChangeRequest),
}


def _denied() -> ProjectError:
    return ProjectError('CAPABILITY_SCOPE_DENIED', '执行能力请求与当前任务不一致', 403)


def _camel(name: str) -> str:
    first, *rest = name.split('_')
    return first + ''.join(part.capitalize() for part in rest)


def json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


class ProjectWorkerCapabilities:
    def __init__(self, sessions: Any) -> None:
        self.sessions = sessions
        self.data = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(sessions))

    async def handle(self, run_id: str, generation: int, request: dict[str, Any]) -> Any:
        if type(generation) is not int or generation < 1:
            raise _denied()
        if request.get('attempt') != 1 or type(request.get('attempt')) is not int:
            raise _denied()
        visit = request.get('nodeVisitId')
        if not isinstance(visit, str) or request.get('commandId') != project_command_id(run_id, generation, visit):
            raise _denied()
        with self.sessions() as session:
            run = session.get(WorkflowRunRow, run_id)
            task = session.scalar(select(ProjectTaskRow).where(ProjectTaskRow.run_id == run_id))
            if run is None or task is None or run.execution_generation != generation or run.status != 'running':
                raise _denied()
            prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
            assert prepared is not None
            node = next((node for node in prepared.execution_plan['nodes'] if node['nodeId'] == request.get('nodeId')), None)
            config = node['data'].get('config', node['data']) if node else {}
            if node is None or node['moduleType'] != 'project_data' or config.get('operation') != request.get('operation'):
                raise _denied()
            event = session.scalar(select(WorkflowRunEventRow).where(
                WorkflowRunEventRow.run_id == run_id,
                WorkflowRunEventRow.execution_generation == generation,
                WorkflowRunEventRow.node_id == request.get('nodeId'),
                WorkflowRunEventRow.node_visit_id == visit,
                WorkflowRunEventRow.attempt == 1,
                WorkflowRunEventRow.kind == 'nodeAttempt',
            ).order_by(WorkflowRunEventRow.sequence.desc()).limit(1))
            if event is None or event.payload.get('status') != 'started':
                raise _denied()
            project_id, task_id = task.project_id, task.id
            if request['operation'] == 'inputs':
                if request.get('arguments') != {}:
                    raise _denied()
                snapshot = session.scalar(select(ProjectTaskInputSnapshotRow).where(ProjectTaskInputSnapshotRow.task_id == task_id))
                assert snapshot is not None
                return json_value(snapshot.inputs)
        arguments = request.get('arguments')
        if not isinstance(arguments, dict) or set(arguments) & {'projectId', 'executionGeneration', 'operationId'}:
            raise _denied()
        selected = DATA_COMMANDS.get(request['operation'])
        if selected is None:
            raise _denied()
        method, model = selected
        names = {_camel(field.name): field.name for field in fields(model)}
        if set(arguments) - names.keys():
            raise _denied()
        values = {names[name]: value for name, value in arguments.items()}
        for name, value in [('execution_generation', generation), ('operation_id', request['commandId']), ('project_id', project_id)]:
            if name in names.values():
                values[name] = value
        try:
            if 'record_ref' in values:
                ref = values['record_ref']
                if not isinstance(ref, dict) or set(ref) != {'projectId', 'tableId', 'datasetGeneration', 'recordKey'}:
                    raise _denied()
                values['record_ref'] = RecordRef(ref['projectId'], ref['tableId'], ref['datasetGeneration'], RecordKey(**ref['recordKey']))
            command = model(**values)
        except (TypeError, KeyError, ValueError) as error:
            raise ProjectError('CAPABILITY_REQUEST_INVALID', '执行能力参数无效', 422) from error
        scope = self.data.scope(project_id, task_id, run_id)
        result = getattr(self.data, method)(scope, command)
        # Mutations return (original result, replayed); the wire result is stable on replay.
        return json_value(result[0] if isinstance(result, tuple) else result)
