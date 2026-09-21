"""Frozen declarations for a live project manual checkpoint."""
from __future__ import annotations

import math
from typing import Any

from autoflow.domain.projects.models import ProjectError

from .graph import parse_workflow
from .models import WorkflowError
from .validation import _strict_json

_TYPES = {'string', 'number', 'integer', 'boolean', 'array', 'object'}
_RESERVED = {'capabilities', 'executionGeneration', 'runId', 'taskId', 'projectId', 'cancellation', 'browser', 'loop_index', 'loop_item', 'loop_key', 'loop_value'}


def _name(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith('__') and value not in _RESERVED


def _typed(value: Any, kind: str) -> bool:
    if not _strict_json(value):
        return False
    if kind == 'number':
        return type(value) is int or type(value) is float and math.isfinite(value)
    return type(value) is {'string': str, 'integer': int, 'boolean': bool, 'array': list, 'object': dict}.get(kind)


def validate_declaration(config: dict[str, Any], node_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    def reject(detail: str) -> None:
        raise WorkflowError('WORKFLOW_NOT_RUNNABLE', f'人工节点 {node_id}: {detail}', 422)

    fields, targets = config.get('inputSchema', []), config.get('resumeTargets', [])
    if not isinstance(fields, list) or not isinstance(targets, list):
        reject('inputSchema 和 resumeTargets 必须为数组')
    names: set[str] = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) - {'name', 'type', 'required', 'enum', 'title'} or not _name(field.get('name')) or not isinstance(field.get('type'), str) or field.get('type') not in _TYPES or type(field.get('required', False)) is not bool:
            reject('输入声明无效或名称受保护')
        if field['name'] in names:
            reject('输入名称重复')
        names.add(field['name'])
        if 'enum' in field and (not isinstance(field['enum'], list) or not field['enum'] or any(not _typed(value, field['type']) for value in field['enum'])):
            reject('枚举值与声明类型不一致')
        if 'title' in field and not isinstance(field['title'], str):
            reject('输入标题必须为字符串')
    by_id = {node['id']: node for node in nodes}
    direct = {edge['target'] for edge in edges if edge['source'] == node_id and edge.get('sourceHandle') not in {'error', 'timeout'}}
    _, graph = parse_workflow({"nodes": nodes, "edges": edges})
    loop_scopes = [graph.loop_body_scope(identity) for identity in graph.loop_branches]
    seen: set[str] = set()
    for target in targets:
        if not isinstance(target, dict) or set(target) - {'nodeId', 'title', 'requiredVariables'} or not isinstance(target.get('nodeId'), str):
            reject('继续目标声明无效')
        identity = target['nodeId']
        if identity in seen or identity not in direct or by_id[identity]['data']['moduleType'] in {'project_end', 'loop', 'foreach', 'foreach_dict', 'break_loop', 'continue_loop'} or sum(edge['target'] == identity for edge in edges) != 1:
            reject('继续目标必须是同一范围的直接后继，不能跳到循环边界、End 或 join')
        if any((node_id in scope) != (identity in scope) for scope in loop_scopes):
            reject('继续目标不能跨越循环范围')
        required = target.get('requiredVariables', [])
        if not isinstance(required, list) or any(not _name(name) for name in required) or ('title' in target and not isinstance(target['title'], str)):
            reject('继续目标前置变量无效')
        seen.add(identity)
    if len(direct) > 1 and seen != direct:
        reject('多个继续后继必须全部显式声明')


def validate_resume(contract: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    def reject(message: str) -> None:
        raise ProjectError('VALIDATION_ERROR', message, 422)

    values = payload.get('inputs', {})
    schema = {field['name']: field for field in contract.get('inputSchema', [])}
    if not isinstance(values, dict) or set(values) - schema.keys():
        reject('人工输入包含未声明字段')
    for name, field in schema.items():
        if name not in values:
            if field.get('required'):
                reject(f'缺少必填输入: {name}')
            continue
        value = values[name]
        if not _typed(value, field['type']) or ('enum' in field and value not in field['enum']):
            reject(f'输入类型或枚举无效: {name}')
        if field.get('required') and isinstance(value, str) and not value.strip():
            reject(f'缺少必填输入: {name}')
    targets = contract.get('resumeTargets', [])
    selected = payload.get('targetNodeId')
    target = next((target for target in targets if target['nodeId'] == selected), None)
    if (selected is not None and target is None) or (len(targets) > 1 and selected is None):
        reject('请选择检查点声明的合法继续位置')
    # Without an alternate selection, a single direct successor keeps its prerequisites.
    target = target or (targets[0] if len(targets) == 1 else {})
    missing = set(target.get('requiredVariables', [])) - set(contract.get('availableVariables', [])) - values.keys()
    if missing:
        reject('继续位置缺少前置变量: ' + ', '.join(sorted(missing)))
    return values
