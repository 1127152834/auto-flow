"""Typed values and condition rules; never evaluate user text as code."""
from copy import deepcopy
from math import isfinite
from typing import Any

from .models import WorkflowError, WorkflowIssue
from .references import is_variable_name

VALUE_OPERATORS = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'contains', 'starts_with', 'ends_with', 'in', 'empty', 'not_empty', 'is_true', 'is_false'}
PAGE_OPERATORS = {'exists', 'not_exists', 'visible', 'not_visible'}
UNARY = {'empty', 'not_empty', 'is_true', 'is_false'}


def fail(code: str, message: str, path: list[str], node_id: str | None = None) -> None:
    raise WorkflowError('WORKFLOW_RUN_INVALID', message, 422, [WorkflowIssue(node_id, path, code, message)])


def numeric(value: Any) -> bool:
    return type(value) is int or type(value) is float and isfinite(value)


def validate_source(source: Any, path: list[str], node_id: str) -> None:
    if not isinstance(source, dict) or source.get('kind') not in ('literal', 'variable'):
        fail('INVALID_VALUE_SOURCE', '请选择固定值或变量', path, node_id)
    if source['kind'] == 'literal':
        if 'value' not in source or set(source) - {'kind', 'value', 'valueType'}:
            fail('INVALID_VALUE_SOURCE', '固定值必须包含 value', path, node_id)
        expected = source.get('valueType')
        if expected is not None:
            value = source['value']
            matches = {'string': type(value) is str, 'number': numeric(value), 'boolean': type(value) is bool, 'array': type(value) is list, 'object': type(value) is dict, 'null': value is None}
            if not isinstance(expected, str) or expected not in matches or not matches[expected]:
                fail('VALUE_TYPE_MISMATCH', '固定值与所选类型不符，请完成输入', [*path, 'value'], node_id)
    else:
        if not is_variable_name(source.get('name')) or set(source) - {'kind', 'name', 'path'}:
            fail('INVALID_VALUE_SOURCE', '请选择有效变量名称', [*path, 'name'], node_id)
        steps = source.get('path', [])
        if not isinstance(steps, list) or len(steps) > 32:
            fail('INVALID_VALUE_PATH', '变量路径最多32层', [*path, 'path'], node_id)
        for i, step in enumerate(steps):
            if not (type(step) is str or type(step) is int and step >= 0):
                fail('INVALID_VALUE_PATH', '字段须为字符串，索引须为非负整数', [*path, 'path', str(i)], node_id)


def value_of(source: dict[str, Any], variables: dict[str, Any], path: list[str], node_id: str) -> Any:
    if source['kind'] == 'literal':
        return deepcopy(source['value'])
    name = source['name']
    if name not in variables:
        fail('VARIABLE_NOT_AVAILABLE', f'变量 {name} 尚未产生', [*path, 'name'], node_id)
    value = variables[name]
    for i, step in enumerate(source.get('path', [])):
        if isinstance(value, dict) and type(step) is str and step in value:  # noqa: SIM114 -- preserve type narrowing for dictionary and list indexing.
            value = value[step]
        elif isinstance(value, list) and type(step) is int and 0 <= step < len(value):
            value = value[step]
        else:
            fail('VARIABLE_PATH_MISSING', '变量字段或列表索引不存在', [*path, 'path', str(i)], node_id)
    return deepcopy(value)


def equal(left: Any, right: Any) -> bool:
    if numeric(left) and numeric(right):
        return bool(left == right)
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right, strict=True))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(value, right[key]) for key, value in left.items())
    return bool(left == right)


def compare(operator: str, left: Any, right: Any, path: list[str], node_id: str) -> bool:
    if operator in {'eq', 'ne'}:
        return equal(left, right) if operator == 'eq' else not equal(left, right)
    if operator in {'empty', 'not_empty'}:
        empty = left is None or isinstance(left, (str, list, dict)) and len(left) == 0
        return empty if operator == 'empty' else not empty
    if operator in {'is_true', 'is_false'}:
        if type(left) is not bool:
            fail('CONDITION_TYPE_MISMATCH', '真假判断需要布尔值', path, node_id)
        return left if operator == 'is_true' else not left
    if operator in {'gt', 'gte', 'lt', 'lte'}:
        if not numeric(left) or not numeric(right):
            fail('CONDITION_TYPE_MISMATCH', '大小比较需要有限数字', path, node_id)
        return {'gt': left > right, 'gte': left >= right, 'lt': left < right, 'lte': left <= right}[operator]
    if operator == 'in':
        if not isinstance(right, list):
            fail('CONDITION_TYPE_MISMATCH', '成员判断的右值必须为列表', path, node_id)
        return any(equal(left, item) for item in right)
    if not isinstance(left, str) or not isinstance(right, str):
        fail('CONDITION_TYPE_MISMATCH', '字符串判断需要字符串', path, node_id)
    return {'contains': lambda: right in left, 'starts_with': lambda: left.startswith(right), 'ends_with': lambda: left.endswith(right)}[operator]()


def set_value(config: dict[str, Any], variables: dict[str, Any], node_id: str) -> None:
    name, operation = config['variableName'], config['operation']
    value = value_of(config['value'], variables, ['config', 'value'], node_id)
    if operation == 'assign':
        variables[name] = value
        return
    if name not in variables:
        fail('VARIABLE_NOT_AVAILABLE', f'变量 {name} 尚未产生', ['config', 'variableName'], node_id)
    current = variables[name]
    if operation == 'append':
        if not isinstance(current, list):
            fail('VARIABLE_TYPE_MISMATCH', '追加目标必须是列表', ['config', 'variableName'], node_id)
        current.append(value)
    else:
        if not numeric(current) or not numeric(value):
            fail('VARIABLE_TYPE_MISMATCH', '增减需要有限数字', ['config', 'value'], node_id)
        result = current + value if operation == 'add' else current - value
        if not numeric(result):
            fail('VARIABLE_TYPE_MISMATCH', '计算结果不是有限数字', ['config', 'value'], node_id)
        variables[name] = result
