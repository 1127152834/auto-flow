"""Route worker requests through authoritative Task/Run capability facts."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import fields, replace
from datetime import datetime
from typing import Any

from sqlalchemy import select, text

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_runs.end import ProjectRunEnd
from autoflow.domain.project_data import capabilities as commands
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.canvas_subflows import CanvasSubflowGraph
from autoflow.domain.workflows.graph import parse_workflow
from autoflow.domain.workflows.parallel_graph import direct_members, structured_fork
from autoflow.domain.workflows.run_validation import STRUCTURE_OPERATIONS
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
)
from autoflow.infrastructure.database.models import ProjectRow
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
from autoflow.infrastructure.process.project_test_browser_worker import wait_for_cleanup

DATA_COMMANDS = {
    'readRecord': ('read_record', commands.ReadProjectRecordRequest),
    'queryRecords': ('query_records', commands.QueryProjectRecordsRequest),
    'queryTableSchema': ('query_table_schema', commands.QueryProjectTableSchemaRequest),
    'createRecord': ('create_record', commands.CreateProjectRecordCommand),
    'updateRecord': ('update_record', commands.UpdateProjectRecordCommand),
    'deleteRecord': ('delete_record', commands.DeleteProjectRecordCommand),
    'setRecordStatus': ('set_record_status', commands.SetRecordStatusCommand),
}


async def _finish_retention(
    callback: Callable[..., Any], *args: Any
) -> Any:
    task = asyncio.create_task(asyncio.to_thread(callback, *args))
    try:
        return await asyncio.shield(task)
    finally:
        # An accepted filesystem save owns its work copy until publication settles.
        await wait_for_cleanup(task)


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


def _node_data_scope(
    scope: commands.TaskCapabilityScope,
    config: dict[str, Any],
    project_id: str,
    operation: str,
) -> commands.TaskCapabilityScope:
    """Reduce the task-level union grant to this frozen node declaration."""
    declared = config.get("tableGrant")
    if config.get("bindingProjectId") != project_id or not isinstance(declared, dict):
        raise _denied()
    if set(declared) != {
        "tableId",
        "datasetGeneration",
        "operations",
        "fieldIds",
        "readPurposes",
    }:
        raise _denied()
    table_id = declared.get("tableId")
    dataset_generation = declared.get("datasetGeneration")
    operations = declared.get("operations")
    field_ids = declared.get("fieldIds")
    read_purposes = declared.get("readPurposes")
    required_operation = {
        "previewFieldChange": "modifyField",
        "previewFieldDeletion": "deleteField",
    }.get(operation, operation)
    if (
        not isinstance(table_id, str)
        or not table_id
        or not isinstance(dataset_generation, str)
        or not dataset_generation
        or operations != [required_operation]
        or not isinstance(field_ids, list)
        or any(not isinstance(item, str) or not item for item in field_ids)
        or not isinstance(read_purposes, list)
        or any(not isinstance(item, str) or not item for item in read_purposes)
    ):
        raise _denied()
    allowed = commands.TableCapabilityGrant(
        table_id,
        dataset_generation,
        frozenset(operations),
        frozenset(field_ids),
        frozenset(read_purposes),
    )
    if not any(
        grant.table_id == allowed.table_id
        and grant.dataset_generation == allowed.dataset_generation
        and allowed.operations <= grant.operations
        and allowed.field_ids <= grant.field_ids
        and allowed.read_purposes <= grant.read_purposes
        for grant in scope.table_grants
    ):
        raise _denied()
    return replace(
        scope,
        status_record_refs=frozenset(),
        create_record_targets=frozenset(),
        record_read_grants=frozenset(),
        record_write_grants=frozenset(),
        table_grants=frozenset({allowed}),
    )


class ProjectWorkerCapabilities:
    def __init__(self, sessions: Any, environments: Any = None) -> None:
        self.sessions = sessions
        self.environments = environments
        self.project_end = ProjectRunEnd(sessions, environments) if environments else None
        self.browser_dispatcher: Any = None
        from .manual_runtime import ProjectManualRuntime
        self.manual = ProjectManualRuntime(sessions, environments, self.end) if environments else None
        if environments:
            environments.manual_runtime = self.manual
        self.data = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(sessions))

    async def handle(self, run_id: str, generation: int, request: dict[str, Any]) -> Any:
        if request.get('operation') in STRUCTURE_OPERATIONS:
            # Remediation M2 R2-23: also covers runs frozen before the change.
            raise ProjectError('PROJECT_STRUCTURE_OPERATION_REMOVED', '运行中不再修改表结构，请在项目「数据」页维护字段', 422)
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
            if (
                run is None
                or task is None
                or run.execution_generation != generation
                or run.status not in ({'running', 'finishing'} if request.get('operation') == 'end' else {'running'})
            ):
                raise _denied()
            prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
            assert prepared is not None
            node = next((node for node in prepared.execution_plan['nodes'] if node['nodeId'] == request.get('nodeId')), None)
            config = node['data'].get('config', node['data']) if node else {}
            expected_operation = 'initializeBrowser' if node and node['moduleType'] == 'open_page' and run.resource_request.get('browser') == 'node' else 'end' if node and node['moduleType'] == 'project_end' else ('manual' if node and node['moduleType'] == 'project_manual' else config.get('operation'))
            if expected_operation == 'manual' and request.get('operation') == 'manualComplete':
                expected_operation = 'manualComplete'
            if node is None or (node['moduleType'] == 'open_page' and expected_operation != 'initializeBrowser') or node['moduleType'] not in {'project_data', 'project_end', 'project_manual', 'open_page'} or expected_operation != request.get('operation'):
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
        if request['operation'] == 'initializeBrowser':
            if arguments or self.browser_dispatcher is None or in_subflow:
                raise _denied()
            try:
                return await self.browser_dispatcher.initialize_browser(run_id, generation, request['commandId'], lambda: self._prepare_browser(project_id, task_id, run_id, generation, request))
            except WorkflowRuntimeError as error:
                raise ProjectError(error.code, error.message, error.status) from error
        if request['operation'] == 'manual' and self.manual is not None:
            if not isinstance(arguments.get('timeoutSeconds'), (int, float)) or isinstance(arguments['timeoutSeconds'], bool):
                raise _denied()
            request = {**request, 'arguments': {**arguments, 'timeoutSeconds': min(arguments['timeoutSeconds'], manual_limit)}}
            return await self.manual.wait(project_id, task_id, run_id, generation, request)
        if request['operation'] == 'manualComplete' and self.manual is not None:
            return json_value(await _finish_retention(self.manual.complete, project_id, task_id, run_id, generation, request))
        if request['operation'] == 'end':
            if self.project_end is None:
                raise _denied()
            return self.project_end.accept(
                run_id,
                generation,
                {
                    key: request[key]
                    for key in (
                        'nodeId',
                        'nodeVisitId',
                        'attempt',
                        'commandId',
                        'operation',
                        'arguments',
                        'browserClosed',
                    )
                },
            )
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
        scope = _node_data_scope(
            self.data.scope(project_id, task_id, run_id),
            config,
            project_id,
            request["operation"],
        )
        result = getattr(self.data, method)(scope, command)
        # Mutation authority does not imply permission to read the record's
        # other fields. The full snapshot remains in the durable operation.
        value = result[0] if isinstance(result, tuple) else result
        if isinstance(result, tuple) and isinstance(value, dict):
            value = {key: item for key, item in value.items() if key != "values"}
        return json_value(value)

    def _prepare_browser(
        self,
        project_id: str,
        task_id: str,
        run_id: str,
        generation: int,
        request: dict[str, Any],
    ) -> Any:
        if self.environments is None:
            raise _denied()
        with self.sessions() as session:
            session.execute(text('BEGIN IMMEDIATE'))
            project = session.get(ProjectRow, project_id)
            run = session.get(WorkflowRunRow, run_id)
            if project is None or project.lifecycle_state != 'active' or run is None or run.status != 'running' or run.execution_generation != generation:
                raise _denied()
            frozen = run.resource_request.get('nodeBrowserEnvironments', {}).get(request['nodeId'])
            if not frozen or frozen.get('environmentResolution'):
                raise _denied()
            existing = session.scalar(select(ProjectEnvironmentInstanceRow).where(ProjectEnvironmentInstanceRow.project_id == project_id, ProjectEnvironmentInstanceRow.active_task_id == task_id))
            if existing is not None:
                if existing.id != request['commandId'] or existing.active_run_id != run_id:
                    raise ProjectError('BROWSER_INSTANCE_ALREADY_INITIALIZED', '任务已有浏览器实例，请使用当前实例', 409)
            else:
                policy = frozen['environmentPolicy']
                inputs = {policy['inputId']: {'currentEnvironmentId': frozen['environmentRef']['environmentId']}} if policy['source'] == 'inputEnvironment' else None
                self.environments.reserve_task_instance(session, project_id, task_id, run_id, policy, inputs, resource_request=frozen, instance_id=request['commandId'])
                session.commit()
        self.environments.attach_task_instance(project_id, task_id, run_id, frozen['environmentPolicy'])
        return frozen

    def end(
        self,
        project_id: str,
        task_id: str,
        run_id: str,
        generation: int,
        request: dict[str, Any],
        retain: dict[str, Any],
    ) -> Any:
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
        # ManualRuntime verified the durable checkpoint and host intent/expiry.
        # Keep this authorization out of worker/HTTP payloads; the End ledger
        # still checks generation and native quiescence before publication.
        result, _operation, _replayed = self.environments.end(project_id, request['commandId'], {
            'taskId': task_id, 'runId': run_id, 'instanceId': instance.instance_id,
            'expectedUseGeneration': instance.instance_use_generation,
            'executionGeneration': generation, 'retainEnvironment': retain,
        }, trusted_manual=True)
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
