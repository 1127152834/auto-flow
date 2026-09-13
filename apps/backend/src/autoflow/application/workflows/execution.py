"""Sequential structured scheduling inside one owned worker."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from functools import partial
from time import monotonic
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.control_values import (
    UNARY,
    compare,
    fail,
    set_value,
    value_of,
)
from autoflow.domain.workflows.run_validation import resolve_node_config


class _ExecutionFailed(Exception):
    def __init__(self, error: dict[str, Any]):
        self.error = error


class WorkflowExecution:
    def __init__(self, variables: dict[str, Any], emit: Callable[[dict[str, Any]], None],
                 action: Callable[[dict[str, Any], dict[str, Any], float], Awaitable[dict[str, Any] | None]],
                 page_condition: Callable[[dict[str, Any], float], Awaitable[bool]],
                 error_of: Callable[[Exception, str], dict[str, Any]]) -> None:
        self.variables, self.emit = variables, emit
        self.action, self.page_condition, self.error_of = action, page_condition, error_of
        self.count = 0
        self.nodes: dict[str, dict[str, Any]] = {}

    async def run(self, document: dict[str, Any], plan: list[dict[str, Any]]) -> dict[str, Any]:
        self.nodes = {node['id']: node for node in document['nodes']}
        self.emit({'type': 'ready', 'message': '浏览器已启动'})
        try:
            await self._sequence(plan, [])
        except _ExecutionFailed as error:
            return {'state': 'failed', 'error': error.error}
        return {'state': 'succeeded', 'error': None}

    async def _dispatch(self, node_id: str, path: list[dict[str, Any]], operation: Callable[[float], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        await asyncio.sleep(0)
        if self.count >= 100000:
            try:
                fail('EXECUTION_LIMIT_EXCEEDED', '本次运行达到100000次节点调度上限', [], node_id)
            except Exception as exception:  # noqa: BLE001 -- normalize the rejected attempt without scheduling a node.
                error = self.error_of(exception, node_id)
                self.emit({'type': 'log', 'level': 'error', 'nodeId': node_id, 'message': error['message'], 'error': error, 'loopPath': deepcopy(path)})
                raise _ExecutionFailed(error) from None
        self.count += 1
        identity = {'nodeId': node_id, 'executionId': uuid4().hex, 'loopPath': deepcopy(path)}
        start = monotonic()
        self.emit({'type': 'node_started', 'message': '节点开始执行', **identity})
        try:
            deadline = asyncio.get_running_loop().time() + self.nodes[node_id]['config'].get('timeoutSeconds', 60)
            async with asyncio.timeout_at(deadline):
                result = await operation(deadline)
        except asyncio.CancelledError:
            raise
        except Exception as exception:  # noqa: BLE001 -- provider translates sensitive errors at the boundary.
            error = self.error_of(exception, node_id)
            self.emit({'type': 'node_failed', 'level': 'error', 'message': error['message'], 'error': error,
                       'durationMs': round((monotonic() - start) * 1000), **identity})
            raise _ExecutionFailed(error) from None
        artifact = result.get('artifact')
        if artifact is not None:
            artifact.update(executionId=identity['executionId'], loopPath=deepcopy(path))
        self.emit({'type': 'node_succeeded', 'message': result.get('message', '节点执行成功'),
                   'durationMs': round((monotonic() - start) * 1000), **identity, **result})
        return result

    async def _condition(self, node: dict[str, Any], deadline: float) -> bool:
        config = node['config']
        for i, rule in enumerate(config['rules']):
            path = ['config', 'rules', str(i)]
            if rule['kind'] == 'page':
                try:
                    target = resolve_node_config({'id': node['id'], 'type': 'wait_element', 'config': rule}, self.variables)
                    result = await self.page_condition(target, deadline)
                except Exception as exception:  # noqa: BLE001 -- retain precise rule location, not raw browser details.
                    error = self.error_of(exception, node['id'])
                    tail = error['path'][1:] if error['path'][:1] == ['config'] else error['path']
                    fail(error['code'], error['message'], [*path, *tail], node['id'])
            else:
                left = value_of(rule['left'], self.variables, [*path, 'left'], node['id'])
                right = None if rule['operator'] in UNARY else value_of(rule['right'], self.variables, [*path, 'right'], node['id'])
                result = compare(rule['operator'], left, right, path, node['id'])
            if config['match'] == 'all' and not result:
                return False
            if config['match'] == 'any' and result:
                return True
        return config['match'] == 'all'

    async def _unit(self, node: dict[str, Any], deadline: float) -> dict[str, Any]:
        kind = node['type']
        if kind == 'condition':
            branch = 'true' if await self._condition(node, deadline) else 'false'
            return {'branch': branch, 'message': '条件成立' if branch == 'true' else '条件不成立'}
        if kind == 'set_variable':
            set_value(node['config'], self.variables, node['id'])
            return {'message': '运行变量已更新'}
        if kind in {'break_loop', 'continue_loop'}:
            return {'branch': kind, 'message': '退出最近一层循环' if kind == 'break_loop' else '跳过本轮剩余步骤'}
        if kind in {'condition_end', 'loop_end'}:
            return {}
        config = resolve_node_config(node, self.variables)
        artifact = await self.action(node, config, deadline)
        return {'artifact': artifact} if artifact is not None else {}

    async def _sequence(self, steps: list[dict[str, Any]], path: list[dict[str, Any]]) -> str | None:
        for step in steps:
            node = self.nodes[step['nodeId']]
            kind = node['type']
            if kind == 'loop':
                await self._loop(node, step, path)
                continue
            result = await self._dispatch(node['id'], path, partial(self._unit, node))
            if kind in {'break_loop', 'continue_loop'}:
                return kind
            if kind == 'condition':
                transfer = await self._sequence(step[result['branch']], path)
                if transfer:
                    return transfer
                end = self.nodes[step['endNodeId']]
                await self._dispatch(end['id'], path, partial(self._unit, end))
        return None

    async def _loop(self, node: dict[str, Any], step: dict[str, Any], path: list[dict[str, Any]]) -> None:
        c, identifier = node['config'], node['id']
        source: Any = None
        iteration = 0

        async def check(deadline: float) -> dict[str, Any]:
            nonlocal source
            if c['mode'] == 'while':
                active = await self._condition(node, deadline)
            else:
                if iteration == 0:
                    source = value_of(c['source'], self.variables, ['config', 'source'], identifier)
                    if c['mode'] == 'count':
                        if type(source) is not int or source < 0:
                            fail('LOOP_SOURCE_INVALID', '次数须为非负整数', ['config', 'source'], identifier)
                    elif not isinstance(source, list):
                        fail('LOOP_SOURCE_INVALID', '遍历目标必须为列表', ['config', 'source'], identifier)
                    length = source if c['mode'] == 'count' else len(source)
                    if length > c['maxIterations']:
                        fail('LOOP_LIMIT_EXCEEDED', '次数或列表长度超过循环上限', ['config', 'maxIterations'], identifier)
                active = iteration < (source if c['mode'] == 'count' else len(source))
            if active and iteration >= c['maxIterations']:
                fail('LOOP_LIMIT_EXCEEDED', '达到循环上限且条件仍成立', ['config', 'maxIterations'], identifier)
            return {'branch': 'body' if active else 'done', 'message': f'进入第 {iteration + 1} 轮' if active else '循环结束'}

        while (await self._dispatch(identifier, [*path, {'loopNodeId': identifier, 'iteration': iteration + 1}], check))['branch'] == 'body':
            iteration += 1
            local_path = [*path, {'loopNodeId': identifier, 'iteration': iteration}]
            self.variables[c['indexVariable']] = iteration
            if c['mode'] == 'foreach':
                self.variables[c['itemVariable']] = deepcopy(source[iteration - 1])
            try:
                transfer = await self._sequence(step['body'], local_path)
                if transfer == 'break_loop':
                    break
                if transfer != 'continue_loop':
                    end = self.nodes[step['endNodeId']]
                    await self._dispatch(end['id'], local_path, partial(self._unit, end))
            finally:
                self.variables.pop(c['indexVariable'], None)
                if c['mode'] == 'foreach':
                    self.variables.pop(c['itemVariable'], None)
