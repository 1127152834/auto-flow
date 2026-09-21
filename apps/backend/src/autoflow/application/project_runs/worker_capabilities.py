"""Route worker requests through authoritative Task/Run capability facts."""
from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime
from typing import Any

from sqlalchemy import select

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.domain.project_data import capabilities as commands
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.canvas_subflows import CanvasSubflowGraph
from autoflow.domain.workflows.graph import parse_workflow
from autoflow.domain.workflows.parallel_graph import direct_members, structured_fork
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
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
    'queryTableSchema': ('query_table_schema', commands.QueryProjectTableSchemaRequest),
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
    def __init__(self, sessions: Any, environments: Any = None) -> None:
        self.sessions = sessions
        self.environments = environments
        from .manual_runtime import ProjectManualRuntime
        self.manual = ProjectManualRuntime(sessions, environments, self.end) if environments else None
        if environments:
            environments.manual_runtime = self.manual
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
            expected_operation = 'end' if node and node['moduleType'] == 'project_end' else ('manual' if node and node['moduleType'] == 'project_manual' else config.get('operation'))
            if expected_operation == 'manual' and request.get('operation') == 'manualComplete':
                expected_operation = 'manualComplete'
            if node is None or node['moduleType'] not in {'project_data', 'project_end', 'project_manual'} or expected_operation != request.get('operation'):
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
            _authorize_call_path(session, prepared.execution_plan, event)
            in_subflow = any(item.get("kind") == "subflow" for item in event.payload.get("executionContext", {}).get("scopes", []))
            project_id, task_id = task.project_id, task.id
            manual_limit = min(config.get('timeoutSeconds', 1800), run.resource_request.get('manualDeadlineSeconds', 1800)) if expected_operation == 'manual' else None
            if request['operation'] == 'inputs':
                if request.get('arguments') != {}:
                    raise _denied()
                snapshot = session.scalar(select(ProjectTaskInputSnapshotRow).where(ProjectTaskInputSnapshotRow.task_id == task_id))
                assert snapshot is not None
                return json_value(snapshot.inputs)
        arguments = request.get('arguments')
        if not isinstance(arguments, dict) or set(arguments) & {'projectId', 'executionGeneration', 'operationId'}:
            raise _denied()
        if request['operation'] == 'manual' and self.manual is not None:
            if not isinstance(arguments.get('timeoutSeconds'), (int, float)) or isinstance(arguments['timeoutSeconds'], bool):
                raise _denied()
            request = {**request, 'arguments': {**arguments, 'timeoutSeconds': min(arguments['timeoutSeconds'], manual_limit)}}
            return await self.manual.wait(project_id, task_id, run_id, generation, request)
        if request['operation'] == 'manualComplete' and self.manual is not None:
            return json_value(self.manual.complete(project_id, task_id, run_id, generation, request))
        if request['operation'] == 'end':
            if set(arguments) != {'retainEnvironment'}:
                raise _denied()
            return self.end(project_id, task_id, run_id, generation, request, arguments['retainEnvironment'])
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
        if in_subflow:
            # Task grants are an upper bound; a child may use only its frozen
            # node declaration. Keep input-record grants, never legacy table-wide
            # create targets, which would bypass the declared field restriction.
            declared = config.get('tableGrant') or {}
            grants = frozenset(
                replace(grant,
                    operations=grant.operations & frozenset(declared.get('operations', [])),
                    field_ids=grant.field_ids & frozenset(declared.get('fieldIds', [])),
                    read_purposes=grant.read_purposes & frozenset(declared.get('readPurposes', [])))
                for grant in scope.table_grants
                if (grant.table_id, grant.dataset_generation) == (declared.get('tableId'), declared.get('datasetGeneration'))
                and grant.operations & frozenset(declared.get('operations', []))
            )
            scope = replace(scope, table_grants=grants, create_record_targets=frozenset())
        result = getattr(self.data, method)(scope, command)
        # Mutations return (original result, replayed); the wire result is stable on replay.
        return json_value(result[0] if isinstance(result, tuple) else result)

    def end(self, project_id, task_id, run_id, generation, request, retain):
        if request.get('browserClosed') is not True or self.environments is None:
            raise _denied()
        instance = self.environments.environments.find_instance_by_task(project_id, task_id)
        if instance is None or instance.active_run_id != run_id:
            raise _denied()
        if not isinstance(retain, dict) or type(retain.get('enabled')) is not bool:
            raise _denied()
        with self.sessions() as session:
            owned_refs = list(session.scalars(select(ProjectRecordLeaseRow.record_ref).where(
                ProjectRecordLeaseRow.project_id == project_id,
                ProjectRecordLeaseRow.task_id == task_id,
                ProjectRecordLeaseRow.run_id == run_id,
                ProjectRecordLeaseRow.state == 'held',
            )))
        targets = retain.get('recordTargets', [])
        if not isinstance(targets, list) or any(not isinstance(target, dict) or target.get('recordRef') not in owned_refs for target in targets):
            raise _denied()
        # The owned worker has awaited BrowserContext.close. The existing
        # End ledger still verifies filesystem quiescence before publication.
        result, _operation, _replayed = self.environments.end(project_id, request['commandId'], {
            'taskId': task_id, 'runId': run_id, 'instanceId': instance.instance_id,
            'expectedUseGeneration': instance.instance_use_generation,
            'executionGeneration': generation, 'retainEnvironment': retain,
        })
        return json_value(result)


def _authorize_call_path(session: Any, plan: dict[str, Any], event: WorkflowRunEventRow) -> None:
    document = plan.get('document')
    if not isinstance(document, dict):
        return  # Legacy chain plans cannot contain child calls.
    graph = CanvasSubflowGraph(document)
    members = {node['id'] for node in graph.top_level_document()['nodes']}
    by_id = {node['id']: node for node in document['nodes']}
    context = event.payload.get('executionContext', {})
    if not isinstance(context, dict):
        raise _denied()
    scopes = context.get('scopes', [])
    if not isinstance(scopes, list) or len(scopes) > 32:
        raise _denied()
    for index, scope in enumerate(scopes):
        _, scope_graph = parse_workflow(graph._subset(members))
        if not isinstance(scope, dict) or scope.get('kind') not in {'subflow', 'parallel'} or not isinstance(scope.get('callNodeId'), str) or not isinstance(scope.get('callVisitId'), str) or scope.get('callNodeId') not in direct_members(scope_graph):
            raise _denied()
        call = by_id[scope['callNodeId']]['data']
        config = call.get('config', call)
        if scope['kind'] == 'subflow':
            if call.get('moduleType') != 'subflow':
                raise _denied()
            definition = graph._find_definition(config.get('subflowGroupId', ''), config.get('subflowName', ''))
            if definition is None or definition['id'] != scope.get('id'):
                raise _denied()
            child_members = graph._members(definition)
        else:
            if 'parallel' not in config:
                raise _denied()
            fork = structured_fork(scope_graph, scope['callNodeId'])
            branch = scope.get('branchNodeId')
            if not isinstance(branch, str) or branch not in fork.branches or scope.get('id') != scope['callNodeId'] or scope.get('joinNodeId') != fork.join_id:
                raise _denied()
            child_members = fork.branches[branch]
        parent = session.scalar(select(WorkflowRunEventRow).where(
            WorkflowRunEventRow.run_id == event.run_id,
            WorkflowRunEventRow.execution_generation == event.execution_generation,
            WorkflowRunEventRow.node_id == scope['callNodeId'],
            WorkflowRunEventRow.node_visit_id == scope.get('callVisitId'),
            WorkflowRunEventRow.attempt == 1,
            WorkflowRunEventRow.kind == 'nodeAttempt',
        ).order_by(WorkflowRunEventRow.sequence.desc()).limit(1))
        if parent is None or parent.payload.get('status') != 'started' or parent.payload.get('executionContext', {}).get('scopes', []) != scopes[:index]:
            raise _denied()
        members = child_members
    _, scope_graph = parse_workflow(graph._subset(members))
    if event.node_id not in direct_members(scope_graph):
        raise _denied()
