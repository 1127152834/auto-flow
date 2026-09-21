"""Live-worker continuation backed by the existing manual and command ledgers."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text

from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.manual_contract import validate_resume
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
    ProjectManualItemRow,
)
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class ProjectManualRuntime:
    def __init__(self, sessions, environments, end):
        self.sessions, self.environments, self.end = sessions, environments, end
        self.dispatcher: Any = None

    def checkpoint(self, item):
        with self.sessions() as session:
            return session.scalar(select(WorkflowRunEventRow).where(
                WorkflowRunEventRow.run_id == item['runId'],
                WorkflowRunEventRow.kind == 'checkpoint',
                WorkflowRunEventRow.payload['manualItemId'].as_string() == item['manualItemId'],
            ).order_by(WorkflowRunEventRow.sequence.desc()).limit(1))

    def describe(self, item):
        checkpoint = self.checkpoint(item)
        if checkpoint is None:
            return item
        return {**item, 'inputSchema': checkpoint.payload.get('inputSchema', []), 'canResume': True}

    def owns(self, item):
        checkpoint = self.checkpoint(item)
        if checkpoint is not None:
            return True
        # A request can race the initial checkpoint commit. Never let that
        # production item fall through to the isolated/manual-only command path.
        with self.sessions() as session:
            run = session.get(WorkflowRunRow, item['runId'])
            prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id) if run else None
            return prepared is not None and any(node.get('moduleType') == 'project_manual' for node in prepared.execution_plan.get('nodes', []))

    def command(self, project_id, key, item, payload, action):
        """CAS a durable intent; only the owning worker may close/save/continue."""
        self.environments._writable(project_id)
        checkpoint = self.checkpoint(item)
        if checkpoint is None or checkpoint.payload.get('manualItemId') != item['manualItemId']:
            raise ProjectError('MANUAL_TRANSITION_LOST', '人工检查点不存在', 409)
        if action == 'resume':
            validate_resume(checkpoint.payload, payload)
        kind = 'resumeManual' if action == 'resume' else 'finishManual'
        operation = self.environments._command(key, kind, project_id, item['instanceId'], {
            'scope': kind, 'projectId': project_id, 'manualItemId': item['manualItemId'], 'request': payload,
        }, datetime.now(UTC))
        accepted, replayed = self.environments.environments.accept_operation(operation)
        if replayed:
            return accepted.result, accepted, True
        try:
            with self.sessions() as session:
                session.execute(text('BEGIN IMMEDIATE'))
                row = session.get(ProjectManualItemRow, item['manualItemId'])
                run = session.get(WorkflowRunRow, item['runId'])
                instance = session.get(ProjectEnvironmentInstanceRow, row.instance_id) if row and row.instance_id else None
                expected_checkpoint = payload.get('checkpointRevision', payload.get('expectedCheckpointRevision'))
                if (row is None or run is None or run.status != 'waiting_manual'
                    or instance is None or instance.active_run_id != run.id or instance.active_task_id != row.task_id or instance.state != 'waiting_manual'
                    or run.execution_generation != checkpoint.execution_generation
                    or row.status != 'waiting' or row.status_revision != payload['expectedStatusRevision']
                    or row.checkpoint_revision != expected_checkpoint
                    or _aware(row.expires_at) <= datetime.now(UTC)):
                    raise ProjectError('MANUAL_TRANSITION_LOST', '人工处理已变化、过期或执行已中断', 409)
                row.status, row.status_revision = 'resume_requested', row.status_revision + 1
                row.updated_at = datetime.now(UTC)
                intent = session.get(ProjectOperationRow, accepted.operation_id)
                assert intent is not None
                intent.result = {'runtimeManual': {'manualItemId': row.id, 'action': action, 'payload': payload, 'executionGeneration': run.execution_generation}}
                session.commit()
        except ProjectError as error:
            self.environments.environments.complete_operation(accepted, None, {'code': error.code, 'message': error.message}, datetime.now(UTC))
            raise
        pending = self.environments.environments.operation_by_key(key)
        return None, pending, False

    def _intent(self, item_id):
        with self.sessions() as session:
            rows = session.scalars(select(ProjectOperationRow).where(
                ProjectOperationRow.kind.in_(['resumeManual', 'finishManual']),
                ProjectOperationRow.status == 'running',
            ))
            return next((row for row in rows if row.result and row.result.get('runtimeManual', {}).get('manualItemId') == item_id), None)

    async def wait(self, project_id, task_id, run_id, generation, request):
        instance = self.environments.environments.find_instance_by_task(project_id, task_id)
        if instance is None or instance.active_run_id != run_id:
            raise ProjectError('CAPABILITY_SCOPE_DENIED', '人工处理实例与任务不一致', 403)
        args = request['arguments']
        if set(args) - {'reason', 'timeoutSeconds', 'availableVariables'} or not {'reason', 'timeoutSeconds'} <= set(args) or not isinstance(args.get('availableVariables', []), list) or any(not isinstance(name, str) for name in args.get('availableVariables', [])) or not isinstance(args['reason'], str) or type(args['timeoutSeconds']) not in {int, float} or not 0 < args['timeoutSeconds'] <= 86400:
            raise ProjectError('CAPABILITY_REQUEST_INVALID', '人工处理配置无效', 422)
        with self.sessions() as session:
            previous = session.scalar(select(WorkflowRunEventRow).where(WorkflowRunEventRow.run_id == run_id, WorkflowRunEventRow.node_visit_id == request['nodeVisitId'], WorkflowRunEventRow.kind == 'checkpoint'))
            if previous is not None:
                raise ProjectError('MANUAL_TRANSITION_LOST', '该节点访问已建立人工检查点', 409)
        with self.sessions() as session:
            run = session.get(WorkflowRunRow, run_id)
            prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
            node = next(node for node in prepared.execution_plan['nodes'] if node['nodeId'] == request['nodeId'])
            config = node['data'].get('config', node['data'])
            contract = {'inputSchema': config.get('inputSchema', []), 'resumeTargets': config.get('resumeTargets', []), 'availableVariables': args.get('availableVariables', [])}
        item = self.environments.open_manual(project_id, {
            'taskId': task_id, 'runId': run_id, 'instanceId': instance.instance_id,
            'checkpointRevision': 1, 'reason': args['reason'],
            'allowedTargets': contract['resumeTargets'],
            'expiresAt': datetime.now(UTC) + timedelta(seconds=args['timeoutSeconds']),
        })
        with self.sessions() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            repository.append_event({
                'eventId': str(uuid4()), 'runId': run_id, 'executionGeneration': generation,
                'kind': 'checkpoint', 'nodeId': request['nodeId'], 'nodeVisitId': request['nodeVisitId'], 'attempt': 1,
                'occurredAt': datetime.now(UTC), 'payload': {
                    'version': 1, 'manualItemId': item['manualItemId'], 'checkpointRevision': 1,
                    **contract,
                    'continuation': 'liveWorker', 'preparedContentId': repository.get_run(run_id=run_id).prepared_content_id,
                },
            })
            session.commit()
        self.dispatcher.pause_manual(run_id, generation)
        try:
            while True:
                run = self.dispatcher.query_run(run_id)
                if run.execution_generation != generation or run.status != 'waiting_manual':
                    return {'action': 'cancel'}
                current = self.environments.get_manual(project_id, item['manualItemId'])
                intent = self._intent(item['manualItemId'])
                if intent is not None:
                    # The HTTP handler may have accepted the intent after the
                    # preceding item read. Use its committed row revision.
                    current = self.environments.get_manual(project_id, item['manualItemId'])
                    decision = intent.result['runtimeManual']
                    if decision['action'] == 'resume':
                        try:
                            resumed = self.environments.begin_resume(project_id, current['manualItemId'], current['statusRevision'])
                        except ProjectError as error:
                            if error.code == 'MANUAL_TRANSITION_LOST':
                                continue
                            raise
                        self.dispatcher.resume_manual(run_id, generation)
                        operation = self.environments.environments.operation_by_key(intent.idempotency_key)
                        self.environments.environments.complete_operation(operation, {'item': resumed, 'run': {'runId': run_id, 'status': 'running'}}, None, datetime.now(UTC))
                        return {'action': 'resume', 'inputs': decision['payload'].get('inputs', {}), 'targetNodeId': decision['payload'].get('targetNodeId')}
                    self.dispatcher.resume_manual(run_id, generation)
                    return {'action': 'finish'}
                if _aware(datetime.fromisoformat(item['expiresAt'])) <= datetime.now(UTC):
                    if current['status'] != 'waiting':
                        await asyncio.sleep(.05)
                        continue
                    # A resume may commit after the intent read above. Claim
                    # expiry with the same row revision before releasing the
                    # worker; the losing decision must re-read the winner.
                    try:
                        self.environments.environments.transition_manual(
                            project_id, item['manualItemId'], 'expired',
                            expected_status_revision=current['statusRevision'],
                        )
                    except ProjectError as error:
                        if error.code == 'MANUAL_TRANSITION_LOST':
                            continue
                        raise
                    self.dispatcher.resume_manual(run_id, generation)
                    return {'action': 'expired'}
                await asyncio.sleep(.05)
        finally:
            run = self.dispatcher.query_run(run_id)
            if run.execution_generation != generation or run.status not in {'running', 'waiting_manual'}:
                self.cancel_run(run_id)

    def complete(self, project_id, task_id, run_id, generation, request):
        with self.sessions() as session:
            checkpoint = session.scalar(select(WorkflowRunEventRow).where(
                WorkflowRunEventRow.run_id == run_id, WorkflowRunEventRow.node_visit_id == request['nodeVisitId'],
                WorkflowRunEventRow.kind == 'checkpoint', WorkflowRunEventRow.execution_generation == generation,
            ))
        if checkpoint is None or request.get('browserClosed') is not True or request['arguments'] != {}:
            raise ProjectError('CAPABILITY_SCOPE_DENIED', '人工收尾缺少关闭确认或检查点', 403)
        item = self.environments.get_manual(project_id, checkpoint.payload['manualItemId'])
        intent = self._intent(item['manualItemId'])
        if intent is None and _aware(item['expiresAt']) > datetime.now(UTC):
            raise ProjectError('CAPABILITY_SCOPE_DENIED', '人工处理尚未作出终结决定', 403)
        payload = intent.result['runtimeManual']['payload'] if intent else {}
        retain = payload.get('retainEnvironment', {'enabled': False})
        try:
            result = self.end(project_id, task_id, run_id, generation, request, retain)
        except ProjectError as error:
            if intent:
                operation = self.environments.environments.operation_by_key(intent.idempotency_key)
                self.environments.environments.complete_operation(operation, None, {'code': error.code, 'message': error.message}, datetime.now(UTC))
            if item['status'] != 'expired':
                self.environments.cancel_manual(project_id, item['manualItemId'], item['statusRevision'])
            return {'action': 'finish', 'outcome': 'failed', 'complete': False}
        status = 'resolved' if intent else 'expired'
        resolved = item if item['status'] == status else self.environments.environments.transition_manual(project_id, item['manualItemId'], status, expected_status_revision=item['statusRevision'])
        outcome = payload.get('outcome', 'timed_out') if result.get('complete') else 'failed'
        if intent:
            operation = self.environments.environments.operation_by_key(intent.idempotency_key)
            self.environments.environments.complete_operation(operation, {'item': resolved, 'run': {'runId': run_id, 'status': outcome}, 'end': result}, None if result.get('complete') else {'code': 'ENVIRONMENT_END_INCOMPLETE', 'message': '环境收尾未完成'}, datetime.now(UTC))
        return {'action': 'finish', 'outcome': outcome, 'complete': result.get('complete', False)}

    def cancel_run(self, run_id):
        with self.sessions() as session:
            ids = list(session.scalars(select(ProjectManualItemRow.id).where(ProjectManualItemRow.run_id == run_id, ProjectManualItemRow.status.in_(['waiting', 'resume_requested']))))
        for identity in ids:
            with self.sessions() as session:
                row = session.get(ProjectManualItemRow, identity)
                if row is None:
                    continue
                project_id, revision = row.project_id, row.status_revision
            try:
                self.environments.cancel_manual(project_id, identity, revision)
            except ProjectError:
                continue
            intent = self._intent(identity)
            if intent:
                operation = self.environments.environments.operation_by_key(intent.idempotency_key)
                self.environments.environments.complete_operation(operation, None, {'code': 'EXECUTION_GENERATION_REVOKED', 'message': '执行已中断，人工命令未执行'}, datetime.now(UTC))
