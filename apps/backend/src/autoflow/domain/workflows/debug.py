"""Compile direct-entry debugging without manufacturing nested execution state."""
import json
from copy import deepcopy
from typing import Any

from .catalog import node_catalog
from .control import compile_control
from .models import WorkflowError, WorkflowIssue
from .references import is_variable_name
from .run_validation import PreparedWorkflow, initial_values, prepare_run
from .validation import validate_structure


def prepare_debug(document: dict[str, Any], layout: dict[str, Any], options: dict[str, Any]) -> PreparedWorkflow:
    validate_structure(document, layout)
    effective = deepcopy(document)
    effective['schemaVersion'] = max(2, effective.get('schemaVersion', 1))
    definitions = {item['type']: item['defaultConfig'] for item in node_catalog()}
    for node in effective['nodes']:
        node['config'] = {**deepcopy(definitions[node['type']]), **node['config']}
    for node in effective['nodes']:
        config, kind = node['config'], node['type']
        fields = ['endNodeId'] if kind in {'condition', 'loop'} else ['ownerNodeId'] if kind in {'condition_end', 'loop_end'} else []
        if kind == 'loop':
            fields += ['indexVariable'] + (['itemVariable'] if config.get('mode') == 'foreach' else [])
            if config.get('mode') not in ('count', 'foreach', 'while'):
                fields.append('mode')
        for field in fields:
            value = config.get(field)
            valid = isinstance(value, str) and bool(value) and (field not in {'indexVariable', 'itemVariable'} or is_variable_name(value))
            if field == 'mode' or not valid:
                raise WorkflowError('WORKFLOW_RUN_INVALID', '控制块结构配置无效', 422,
                                    [WorkflowIssue(node['id'], ['config', field], 'CONTROL_CONFIG_INVALID', '请填写有效的控制块配置')])
    plan = compile_control(effective, check_variables=False)
    node_ids = {n['id'] for n in effective['nodes']}
    target = options.get('targetNodeId')
    if not set(options.get('breakpoints', [])) <= node_ids or options['start'] != 'entry' and target not in node_ids:
        raise WorkflowError('DEBUG_NODE_INVALID', '调试目标或断点不属于此流程', 422)
    values = options.get('values', {})
    reserved = {n['config'][key] for n in effective['nodes'] if n['type'] == 'loop' for key in (('indexVariable', 'itemVariable') if n['config'].get('mode') == 'foreach' else ('indexVariable',)) if key in n['config']}
    validate_values(values, reserved)
    variables = {**initial_values(effective), **deepcopy(values)}
    if options['start'] == 'node':
        index = next((i for i, step in enumerate(plan) if step['nodeId'] == target), None)
        if index is None:
            raise WorkflowError('DEBUG_START_INVALID', '只能从顶层普通节点或控制块起点直接起跑', 422,
                                [WorkflowIssue(target, ['debug', 'targetNodeId'], 'DEBUG_START_INVALID', '嵌套节点请使用运行至此')])
        plan = plan[index:]
    selected: set[str] = set()

    def collect(steps: list[dict[str, Any]]) -> None:
        for step in steps:
            selected.add(step['nodeId'])
            if 'endNodeId' in step:
                selected.add(step['endNodeId'])
            for key in ('body', 'true', 'false'):
                collect(step.get(key, []))
    collect(plan)
    subset = {**effective, 'nodes': [n for n in effective['nodes'] if n['id'] in selected],
              'edges': [e for e in effective['edges'] if e['source'] in selected and e['target'] in selected],
              'variables': [{'name': name, 'type': 'string', 'value': ''} for name in variables]}
    # Validate declared initial types separately; literal debug overrides can change runtime types.
    from .validation import workflow_issues
    declaration_issues = [i for i in workflow_issues({**effective, 'nodes': [], 'edges': []}) if i.path[:1] == ['variables']]
    if declaration_issues:
        raise WorkflowError('WORKFLOW_RUN_INVALID', '变量声明初值无效', 422, declaration_issues)
    checked = prepare_run(subset, {**layout, 'breakpoints': [key for key in layout.get('breakpoints', []) if key in selected], 'nodes': {key: value for key, value in layout['nodes'].items() if key in selected}}, allow_missing_pages=options['start'] == 'node')
    return PreparedWorkflow(effective, checked.node_ids, variables, checked.warnings, checked.plan, deepcopy(options))


def validate_values(values: dict[str, Any], reserved: set[str]) -> None:
    if any(not is_variable_name(name) or name in reserved for name in values):
        raise WorkflowError('DEBUG_VARIABLE_INVALID', '变量名称无效或与只读循环变量冲突', 422)
    try:
        json.dumps(values, allow_nan=False)
    except (TypeError, ValueError):
        raise WorkflowError('DEBUG_VALUE_INVALID', '变量必须为有限数字或有效 JSON 值', 422) from None
