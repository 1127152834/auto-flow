"""Compile explicit paired blocks to a bounded, sequential execution plan."""
from typing import Any

from .control_values import (
    PAGE_OPERATORS,
    UNARY,
    VALUE_OPERATORS,
    fail,
    validate_source,
)
from .models import WorkflowError, WorkflowIssue
from .references import REFERENCE_PATTERN, is_variable_name

CONTROL_TYPES = {'condition', 'condition_end', 'loop', 'loop_end', 'break_loop', 'continue_loop', 'set_variable'}
OPENERS = {'condition': 'condition_end', 'loop': 'loop_end'}


def text_references(value: Any, path: list[str], node_id: str | None = None) -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    if isinstance(value, str):
        for match in REFERENCE_PATTERN.finditer(value):
            name = match.group(1) if match.group(1) is not None else match.group(2)
            if is_variable_name(name):
                found.append((name, path))
            elif match.group(1) is not None:
                fail('INVALID_REFERENCE', '变量引用须使用 {变量名} 或 ${变量名}', path, node_id)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(text_references(item, [*path, str(index)], node_id))
    return found


def source_references(source: dict[str, Any], path: list[str]) -> list[tuple[str, list[str]]]:
    return [(source['name'], [*path, 'name'])] if source.get('kind') == 'variable' else []


def node_references(node: dict[str, Any]) -> list[tuple[str, list[str]]]:
    kind, c = node['type'], node['config']
    refs: list[tuple[str, list[str]]] = []
    if kind == 'set_variable':
        refs += source_references(c['value'], ['config', 'value'])
        if c['operation'] != 'assign':
            refs.append((c['variableName'], ['config', 'variableName']))
    elif kind in {'condition', 'loop'}:
        if kind == 'loop' and c['mode'] != 'while':
            refs += source_references(c['source'], ['config', 'source'])
        else:
            for i, rule in enumerate(c['rules']):
                path = ['config', 'rules', str(i)]
                if rule['kind'] == 'page':
                    refs += text_references(rule['selector'], [*path, 'selector'], node['id'])
                    refs += text_references(rule.get('framePath', []), [*path, 'framePath'], node['id'])
                else:
                    refs += source_references(rule['left'], [*path, 'left'])
                    if rule['operator'] not in UNARY:
                        refs += source_references(rule['right'], [*path, 'right'])
    elif kind not in CONTROL_TYPES:
        for field in ('url', 'selector', 'framePath', 'text', 'savePath'):
            if field in {'selector', 'framePath'} and kind == 'screenshot' and c.get('screenshotType', 'fullpage') != 'element':
                continue
            refs += text_references(c.get(field), ['config', field], node['id'])
    return refs


def control_config_issues(node: dict[str, Any]) -> list[WorkflowIssue]:
    c, kind, identifier = node['config'], node['type'], node['id']
    try:
        if kind in OPENERS and not isinstance(c.get('endNodeId'), str):
            fail('BLOCK_PAIR_INVALID', '控制节点缺少结束节点', ['config', 'endNodeId'], identifier)
        if kind.endswith('_end') and not isinstance(c.get('ownerNodeId'), str):
            fail('BLOCK_PAIR_INVALID', '结束节点缺少所属控制节点', ['config', 'ownerNodeId'], identifier)
        if kind == 'set_variable':
            if c.get('operation') not in ('assign', 'add', 'subtract', 'append') or not is_variable_name(c.get('variableName')):
                fail('VARIABLE_CONFIG_INVALID', '请选择变量操作并填写有效名称', ['config'], identifier)
            validate_source(c.get('value'), ['config', 'value'], identifier)
        if kind == 'loop':
            if c.get('mode') not in ('count', 'foreach', 'while'):
                fail('LOOP_MODE_INVALID', '请选择循环类型', ['config', 'mode'], identifier)
            if type(c.get('maxIterations')) is not int or not 1 <= c['maxIterations'] <= 100000:
                fail('LOOP_LIMIT_INVALID', '循环上限须为1至100000的整数', ['config', 'maxIterations'], identifier)
            for field in ('indexVariable', 'itemVariable') if c['mode'] == 'foreach' else ('indexVariable',):
                if not is_variable_name(c.get(field)):
                    fail('LOOP_VARIABLE_INVALID', '循环变量须为有效名称', ['config', field], identifier)
            if c['mode'] != 'while':
                validate_source(c.get('source'), ['config', 'source'], identifier)
        if kind == 'condition' or kind == 'loop' and c.get('mode') == 'while':
            if c.get('match') not in ('all', 'any') or not isinstance(c.get('rules'), list) or not 1 <= len(c['rules']) <= 100:
                fail('CONDITION_RULES_INVALID', '请配置1至100条条件及匹配方式', ['config', 'rules'], identifier)
            for i, rule in enumerate(c['rules']):
                path = ['config', 'rules', str(i)]
                if not isinstance(rule, dict) or rule.get('kind') not in ('value', 'page'):
                    fail('CONDITION_RULE_INVALID', '条件类型无效', path, identifier)
                if rule['kind'] == 'value':
                    if rule.get('operator') not in tuple(VALUE_OPERATORS) or set(rule) - {'kind', 'operator', 'left', 'right'}:
                        fail('CONDITION_OPERATOR_INVALID', '比较方式无效', [*path, 'operator'], identifier)
                    validate_source(rule.get('left'), [*path, 'left'], identifier)
                    if rule['operator'] not in UNARY:
                        validate_source(rule.get('right'), [*path, 'right'], identifier)
                else:
                    if rule.get('operator') not in tuple(PAGE_OPERATORS) or set(rule) - {'kind', 'operator', 'selector', 'framePath'}:
                        fail('CONDITION_OPERATOR_INVALID', '网页比较方式无效', [*path, 'operator'], identifier)
                    if not isinstance(rule.get('selector'), str) or not rule['selector'].strip():
                        fail('REQUIRED', '请填写元素选择器', [*path, 'selector'], identifier)
                    frames = rule.get('framePath', [])
                    if not isinstance(frames, list) or len(frames) > 32:
                        fail('INVALID_FRAME_PATH', '框架路径最多32层', [*path, 'framePath'], identifier)
                    for j, step in enumerate(frames):
                        if not isinstance(step, str) or not step.strip():
                            fail('INVALID_FRAME_PATH', '框架路径须为非空选择器', [*path, 'framePath', str(j)], identifier)
    except WorkflowError as error:
        return error.issues
    return []


def compile_control(document: dict[str, Any], *, check_variables: bool = True) -> list[dict[str, Any]]:
    nodes = {node['id']: node for node in document['nodes']}
    if not nodes:
        fail('EMPTY_WORKFLOW', '请添加流程节点', ['nodes'])
    outgoing: dict[str, dict[str, str]] = {identifier: {} for identifier in nodes}
    incoming: dict[str, int] = dict.fromkeys(nodes, 0)
    for i, edge in enumerate(document['edges']):
        source, target, handle = edge['source'], edge['target'], edge['sourceHandle']
        kind = nodes[source]['type']
        ports = {'true', 'false'} if kind == 'condition' else {'body', 'done'} if kind == 'loop' else set() if kind in {'loop_end', 'break_loop', 'continue_loop'} else {'out'}
        if handle not in ports or edge['targetHandle'] != 'in' or handle in outgoing[source]:
            fail('INVALID_CONTROL_PORT', '端口无效或已连接其他节点', ['edges', str(i)], source)
        outgoing[source][handle] = target
        incoming[target] += 1
        if incoming[target] > 1 and nodes[target]['type'] != 'condition_end':
            fail('CROSS_BLOCK_CONNECTION', '只有条件结束节点允许汇合', ['edges', str(i)], target)
    for node in nodes.values():
        if node['type'] in OPENERS:
            end = nodes.get(node['config'].get('endNodeId'))
            if not end or end['type'] != OPENERS[node['type']] or end['config'].get('ownerNodeId') != node['id']:
                fail('BLOCK_PAIR_INVALID', '起点和结束节点必须正确配对', ['config', 'endNodeId'], node['id'])
    starts = [identifier for identifier in nodes if not incoming[identifier] and nodes[identifier]['type'] not in {'loop_end', 'condition_end'}]
    if len(starts) != 1:
        fail('WORKFLOW_ENTRY_INVALID', '流程必须只有一个入口，且所有节点连入同一流程', ['edges'])
    declarations = {v['name'] for v in document['variables']}
    writers = {n['config']['variableName'] for n in nodes.values() if n['type'] in {'set_variable', 'get_element_info', 'screenshot'} and isinstance(n['config'].get('variableName'), str)}
    visited: set[str] = set()

    def walk(start: str | None, stop: str | None, available: set[str], locals_: set[str], depth: int, in_loop: bool) -> tuple[list[dict[str, Any]], set[str], bool]:
        steps: list[dict[str, Any]] = []
        current = start
        while current != stop:
            if current is None:
                fail('BLOCK_NOT_CONNECTED', '分支或循环体必须连接到所属结束节点', ['edges'], stop)
            assert current is not None
            if current in visited or nodes[current]['type'] in {'condition_end', 'loop_end'}:
                fail('CROSS_BLOCK_CONNECTION', '存在回环、交叉汇合或跨块连线', ['edges'], current)
            visited.add(current)
            node, edges = nodes[current], outgoing[current]
            kind, config = node['type'], node['config']
            if check_variables:
                for name, path in node_references(node):
                    if name not in available:
                        fail('VARIABLE_NOT_AVAILABLE', f'变量 {name} 在此路径尚不可用', path, current)
            if kind in {'set_variable', 'get_element_info', 'screenshot'}:
                target = config['variableName']
                if target in locals_:
                    fail('LOOP_VARIABLE_READ_ONLY', '循环临时变量只读', ['config', 'variableName'], current)
                available = available | {target}
            step: dict[str, Any] = {'nodeId': current}
            steps.append(step)
            if kind in {'break_loop', 'continue_loop'}:
                if not in_loop:
                    fail('LOOP_CONTROL_OUTSIDE', '此节点只能用于循环体', ['type'], current)
                return steps, available, False
            if kind in OPENERS:
                if depth >= 32:
                    fail('BLOCK_DEPTH_EXCEEDED', '控制块最多嵌套32层', ['edges'], current)
                end = config['endNodeId']
                if end in visited:
                    fail('BLOCK_PAIR_INVALID', '结束节点不能由多个控制块共用', ['config', 'endNodeId'], current)
                visited.add(end)
                step['endNodeId'] = end
                if kind == 'condition':
                    if not {'true', 'false'} <= edges.keys():
                        fail('BLOCK_NOT_CONNECTED', '请连接真假两个分支', ['edges'], current)
                    yes, yes_vars, yes_reaches = walk(edges['true'], end, set(available), locals_, depth + 1, in_loop)
                    no, no_vars, no_reaches = walk(edges['false'], end, set(available), locals_, depth + 1, in_loop)
                    step.update(true=yes, false=no)
                    reaching = [v for v, reaches in ((yes_vars, yes_reaches), (no_vars, no_reaches)) if reaches]
                    if not reaching:
                        if outgoing[end]:
                            fail('UNREACHABLE_NODE', '两个分支均退出循环，结束节点不能再连接后继', ['edges'], end)
                        return steps, available, False
                    available = set.intersection(*reaching)
                    current = outgoing[end].get('out')
                else:
                    if 'body' not in edges:
                        fail('BLOCK_NOT_CONNECTED', '请连接循环体', ['edges'], current)
                    local_names = [config['indexVariable']]
                    if config['mode'] == 'foreach':
                        local_names.append(config['itemVariable'])
                    if len(set(local_names)) != len(local_names) or set(local_names) & (declarations | writers | locals_):
                        field = 'indexVariable' if config['indexVariable'] in declarations | writers | locals_ else 'itemVariable'
                        fail('LOOP_VARIABLE_CONFLICT', '循环变量与流程变量、输出或外层变量重名', ['config', field], current)
                    body, _, _ = walk(edges['body'], end, available | set(local_names), locals_ | set(local_names), depth + 1, True)
                    step['body'] = body
                    current = edges.get('done')
            else:
                current = edges.get('out')
        return steps, available, True

    plan, _, _ = walk(starts[0], None, declarations, set(), 0, False)
    remaining = set(nodes) - visited
    if remaining:
        fail('DISCONNECTED_NODE', '节点未连接到有效控制路径', ['edges'], min(remaining))
    return plan
