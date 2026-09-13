"""Node-boundary debug control within the existing sequential execution task."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.debug import validate_values
from autoflow.domain.workflows.models import WorkflowError


class WorkflowDebug:
    def __init__(self, options: dict[str, Any], variables: dict[str, Any],
                 emit: Callable[[dict[str, Any]], None],
                 record: Callable[[str, Any], dict[str, Any]],
                 page_command: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]) -> None:
        self.options, self.variables, self.emit, self.record = options, variables, emit, record
        self.page_command = page_command
        self.state = 'running'
        self.revision = 0
        self.pause_id: str | None = None
        self.identity: dict[str, Any] = {}
        self.breakpoints = set(options.get('breakpoints', []))
        self.target = options.get('targetNodeId') if options.get('start') == 'until' else None
        self.pause_reason: str | None = None
        self.next_reason = 'start'
        self.pause_next = options.get('start', 'entry') != 'until'
        self.permission = asyncio.Event()
        self.lock = asyncio.Lock()
        self.responses: dict[str, dict[str, Any]] = {}
        self.reserved: set[str] = set()
        self.scopes: dict[str, str] = {}
        self.sources: dict[str, str] = {}
        self.failure: dict[str, Any] | None = None
        self.wait_started = 0.0
        self.paused_at: str | None = None
        self.wait_ms = 0
        self.checkpoint_id: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {'state': self.state, 'pauseReason': self.pause_reason, 'controlRevision': self.revision, 'pauseId': self.pause_id,
                'breakpoints': sorted(self.breakpoints), 'pendingNodeId': self.identity.get('nodeId'),
                'pendingExecutionId': self.identity.get('executionId'), 'loopPath': self.identity.get('loopPath', []),
                'checkpointId': self.checkpoint_id, 'pauseDurationMs': self.wait_ms, 'pausedAt': self.paused_at}

    def _event(self, kind: str, message: str, **extra: Any) -> None:
        self.emit({'type': kind, 'message': message, **self.identity, **extra})

    def checkpoint(self, reason: str, replacements: dict[str, Any] | None = None) -> None:
        values = self.variables if replacements is None else {**self.variables, **deepcopy(replacements)}
        sources = self.sources if replacements is None else {**self.sources, **dict.fromkeys(replacements, 'manual')}
        artifact = self.record(self.identity.get('nodeId', ''), {
            'kind': 'checkpoint', 'reason': reason, 'variables': [
                {'name': name, 'value': value, 'scope': self.scopes.get(name), 'source': sources.get(name, 'initial')}
                for name, value in sorted(values.items())], 'modifiedNames': sorted(replacements) if replacements is not None else [], **self.identity})
        if replacements is not None:
            self.variables.update({name: values[name] for name in replacements})
            self.sources.update(sources)
        artifact.update(diagnosticKind='checkpoint', reason=reason, purpose='diagnostic', executionId=self.identity.get('executionId'), loopPath=self.identity.get('loopPath', []))
        self.checkpoint_id = artifact['id']
        self._event('debug_checkpoint', '变量检查点', artifact=artifact, debug=self.snapshot())

    def changes(self, changes: list[dict[str, Any]], source: str = 'node') -> None:
        if not changes:
            return
        for item in changes:
            self.sources[item['name']] = source
        artifact = self.record(self.identity.get('nodeId', ''), {'kind': 'changes', 'changes': changes, 'source': source, **self.identity})
        artifact.update(diagnosticKind='changes', purpose='diagnostic', executionId=self.identity.get('executionId'), loopPath=self.identity.get('loopPath', []))
        self._event('variables_changed', '运行变量发生变化', artifact=artifact)

    async def before(self, identity: dict[str, Any]) -> None:
        self.identity = identity
        target = identity['nodeId'] == self.target
        if target:
            self.target = None
        if self.pause_next or target or identity['nodeId'] in self.breakpoints:
            reason = 'target' if target else 'breakpoint' if identity['nodeId'] in self.breakpoints else self.next_reason
            await self._pause('paused', reason)

    async def _pause(self, state: str, reason: str) -> None:
        self.state, self.pause_id = state, uuid4().hex
        self.pause_reason = reason
        self.pause_next = False
        self.permission.clear()
        self.revision += 1
        self.wait_started = monotonic()
        self.paused_at = datetime.now(UTC).isoformat()
        self.checkpoint(reason)
        self._event('debug_state', '执行失败，浏览器保留供检查' if state == 'failed_paused' else '已暂停在节点执行前', debug=self.snapshot(), reason=reason, error=self.failure)
        await self.permission.wait()

    async def failed(self, error: dict[str, Any]) -> None:
        self.failure = error
        await self._pause('failed_paused', 'failure')

    def finish(self) -> None:
        if self.target:
            self._event('log', '本次路径未到达目标节点', level='warning')
        self.checkpoint('finished')

    async def command(self, command: dict[str, Any]) -> dict[str, Any]:
        async with self.lock:
            identifier = command['commandId']
            if identifier in self.responses:
                return self.responses[identifier]
            try:
                if command['expectedRevision'] != self.revision:
                    raise WorkflowError('DEBUG_REVISION_CONFLICT', '调试状态已变化，请刷新后重试', 409)
                action = command['action']
                paused = self.state in {'paused', 'failed_paused'}
                if action not in {'pause', 'breakpoints'} and (not paused or command.get('pauseId') != self.pause_id):
                    raise WorkflowError('DEBUG_PAUSE_CHANGED', '此暂停已结束或尚未暂停', 409)
                if self.state == 'failed_paused' and action not in {'page', 'pages'}:
                    raise WorkflowError('DEBUG_FAILED_READ_ONLY', '失败现场只允许检查和结束调试', 409)
                if action == 'pause':
                    if self.state != 'running':
                        raise WorkflowError('DEBUG_STATE_INVALID', '当前状态不能请求暂停', 409)
                    self.pause_next, self.state = True, 'pausing'
                    self.next_reason = 'pause'
                elif action in {'resume', 'step'}:
                    self.wait_ms += round((monotonic() - self.wait_started) * 1000)
                    self.paused_at = None
                    self.pause_reason = None
                    self.next_reason = 'step'
                    self.pause_next, self.state, self.pause_id = action == 'step', 'running', None
                elif action == 'breakpoints':
                    points = command.get('breakpoints', [])
                    if not set(points) <= self.node_ids:
                        raise WorkflowError('DEBUG_NODE_INVALID', '断点不属于本次运行快照', 422)
                    self.breakpoints = set(points)
                elif action == 'variables':
                    values = command.get('values', {})
                    validate_values(values, self.reserved)
                    self.checkpoint('modified', values)
                elif action in {'page', 'pages'}:
                    async with asyncio.timeout(10):
                        data = await self.page_command(command)
                else:
                    raise WorkflowError('DEBUG_COMMAND_INVALID', '不支持的调试操作', 422)
                self.revision += 1
                response = {'commandId': identifier, 'state': 'applied', 'debug': self.snapshot(), 'data': data if action in {'page', 'pages'} else None, 'error': None}
                self._event('debug_state', '调试控制已应用', debug=self.snapshot())
            except WorkflowError as error:
                response = {'commandId': identifier, 'state': 'rejected', 'debug': self.snapshot(), 'data': None, 'error': {'code': error.code, 'message': error.message}}
            except OSError:
                response = {'commandId': identifier, 'state': 'rejected', 'debug': self.snapshot(), 'data': None, 'error': {'code': 'DEBUG_DIAGNOSTIC_FAILED', 'message': '诊断文件保存失败，变量修改未应用'}}
            except Exception:  # noqa: BLE001 -- browser details stay inside the worker.
                response = {'commandId': identifier, 'state': 'rejected', 'debug': self.snapshot(), 'data': None, 'error': {'code': 'DEBUG_PAGE_FAILED', 'message': '页面已关闭或操作失败'}}
            self.responses[identifier] = response
            self._event('debug_response', '调试命令处理完成', response=response)
            if response['state'] == 'applied' and command['action'] in {'resume', 'step'}:
                self.permission.set()
            return response

    def bind(self, document: dict[str, Any]) -> None:
        self.node_ids = {node['id'] for node in document['nodes']}
        self.reserved = {node['config'][key] for node in document['nodes'] if node['type'] == 'loop'
                         for key in (('indexVariable', 'itemVariable') if node['config'].get('mode') == 'foreach' else ('indexVariable',)) if key in node['config']}
