"""Adapt the shared graph scheduler to the durable project event contract."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
from itertools import pairwise
from time import monotonic
from typing import Any

from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext

from .workflow_executor import WorkflowExecutor
from .workflow_session import CloakBrowserWorkflowSession

_visit: ContextVar[tuple[str, str]] = ContextVar('project_node_visit')


class _ProjectDataNode(ModuleExecutor):
    module_type = 'project_data'

    def __init__(self, request: Callable[..., Awaitable[Any]]) -> None:
        self.request = request

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        node_id, visit = _visit.get()
        reply = await self.request(node_id, visit, config['operation'], context.resolve_value(config.get('arguments', {}), preserve_types=True))
        if 'error' in reply:
            return ModuleResult(False, error=reply['error']['code'])
        value = reply['result']
        if name := config.get('variableName'):
            context.set_variable(name, value)
        return ModuleResult(True, data=value)


class _Cancellation:
    def __init__(self, stopped: Callable[[], bool]) -> None:
        self.stopped = stopped

    @property
    def cancelled(self) -> bool:
        return self.stopped()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError


class _TimedNode(ModuleExecutor):
    def __init__(self, executor: ModuleExecutor) -> None:
        self.executor = executor

    @property
    def module_type(self) -> str:
        return self.executor.module_type

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        # Preserve the project's whole-node timeout, including fractional seconds.
        timeout = config.get('timeout', 0)
        try:
            async with asyncio.timeout(timeout or None):
                return await self.executor.execute(config, context)
        except TimeoutError:
            return ModuleResult(False, error='WORKFLOW_NODE_TIMEOUT', is_timeout=True)


class _LegacyBrowserNode(ModuleExecutor):
    def __init__(self, kind: str, executor: WorkflowExecutor) -> None:
        self.kind, self.executor = kind, executor

    @property
    def module_type(self) -> str:
        return self.kind

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        # Existing project documents use UUID substitutions and append semantics.
        # Reuse their actions while the shared Runtime owns graph traversal.
        try:
            output = await self.executor._execute(self.kind, config)
        except Exception as error:  # noqa: BLE001 -- provider diagnostics become stable codes.
            return ModuleResult(False, error=self.executor._safe_error(error)['code'])
        if output is not None:
            name, value = output
            context.set_variable(name, value)
            return ModuleResult(True, data=value)
        return ModuleResult(True)


class _ProjectRegistry(ExecutorRegistry):
    def __init__(self, legacy: WorkflowExecutor, capability: Callable[..., Awaitable[Any]] | None) -> None:
        super().__init__()
        self.source = build_production_executor_registry()
        self.legacy = legacy
        self.capability = capability

    def get_all_types(self) -> list[str]:
        return [*self.source.get_all_types(), *(['project_data'] if self.capability else [])]

    def get(self, module_type: str) -> ModuleExecutor | None:
        executor: ModuleExecutor | None
        if module_type == 'project_data' and self.capability is not None:
            executor = _ProjectDataNode(self.capability)
        elif module_type in {'open_page', 'input_text', 'click_element', 'get_element_info'}:
            executor = _LegacyBrowserNode(module_type, self.legacy)
        else:
            executor = self.source.get(module_type)
        return _TimedNode(executor) if executor is not None else None


class ProjectGraphExecutor:
    def __init__(
        self, browser_context: Any, variables: Mapping[str, Any],
        emit: Callable[[str, str, str, dict[str, object]], Awaitable[None]],
        should_stop: Callable[[], bool],
        capture_failure: Callable[[Any, str, str], Awaitable[dict[str, object]]] | None = None,
        capability: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self.browser = CloakBrowserWorkflowSession(browser_context) if browser_context is not None else None
        self.cancellation = _Cancellation(should_stop)
        self.context = ExecutionContext(variables=dict(variables), browser=self.browser, cancellation=self.cancellation, events=self)
        self.legacy = WorkflowExecutor(browser_context, variables, emit, should_stop)
        self.legacy.variables = self.context.variables
        self.emit = emit
        self.capture_failure = capture_failure
        self.capability = capability
        self.nodes: dict[str, Any] = {}
        self.started: dict[str, float] = {}
        self.error: dict[str, str] | None = None

    async def run(self, plan: Mapping[str, Any]) -> dict[str, object]:
        document = plan.get('document')
        if not isinstance(document, dict):
            # Previously frozen chain/v1 content remains executable without a migration.
            identities = plan['orderedNodeIds']
            document = {
                'nodes': [{'id': node['nodeId'], 'data': {**node['data'], 'moduleType': node['moduleType']}} for node in plan['nodes']],
                'edges': [{'id': f'edge-{index}', 'source': source, 'target': target} for index, (source, target) in enumerate(pairwise(identities))],
            }
        self.nodes = {node['id']: node['data'] for node in document['nodes']}
        result = await WorkflowRuntime(_ProjectRegistry(self.legacy, self.capability)).execute(document, self.context)
        if not result.success and self.error is None:
            self.error = {'code': 'WORKFLOW_NODE_INVALID', 'message': '工作流包含不可执行的节点'}
        return {'status': 'succeeded' if result.success else 'failed', 'error': self.error}

    async def publish(self, event: Mapping[str, Any]) -> None:
        node_id, visit = event['nodeId'], event['executionId']
        if event['type'] == 'execution:node_start':
            _visit.set((node_id, visit))
            self.started[visit] = monotonic()
            await self.emit('nodeAttempt', node_id, visit, {'status': 'started'})
            self.cancellation.raise_if_cancelled()
            await self.emit('log', node_id, visit, {'level': 'info', 'message': '开始执行节点'})
            self.cancellation.raise_if_cancelled()
            return
        if event['type'] != 'execution:node_complete':
            return
        duration = round((monotonic() - self.started.pop(visit)) * 1000)
        success = bool(event['success'])
        payload: dict[str, object] = {'status': 'succeeded' if success else 'failed', 'durationMs': duration}
        if success:
            data = self.nodes[node_id]
            config = data.get('config', data)
            name = config.get('variableName')
            if name and event.get('data') is not None:
                await self.emit('output', node_id, visit, {'name': name, 'value': event['data']})
            await self.emit('log', node_id, visit, {'level': 'info', 'message': '节点执行完成'})
        else:
            timeout = event.get('error') == 'WORKFLOW_NODE_TIMEOUT'
            self.error = {'code': 'WORKFLOW_NODE_TIMEOUT' if timeout else 'WORKFLOW_NODE_FAILED', 'message': '工作流节点执行超时' if timeout else '工作流节点执行失败'}
            payload['error'] = self.error
            await self.emit('log', node_id, visit, {'level': 'error', 'message': self.error['message']})
        await self.emit('nodeAttempt', node_id, visit, payload)
        if not success and self.capture_failure is not None:
            try:
                page = self.legacy.page
            except Exception:  # noqa: BLE001 -- absence of a page is valid failure evidence.
                page = None
            await self.emit('artifact', node_id, visit, await self.capture_failure(page, node_id, visit))
