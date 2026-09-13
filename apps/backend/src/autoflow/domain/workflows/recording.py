"""Recording drafts compile into ordinary, independently executable workflow nodes."""
from copy import deepcopy
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .catalog import node_catalog
from .control import compile_control
from .models import WorkflowError
from .references import literal_eligible
from .validation import validate_structure

MAX_VALUE_BYTES = 1024 * 1024
MAX_STEPS = 10000
MAX_RECORDING_BYTES = 64 * 1024 * 1024
ACTIONS = {'navigate', 'click', 'dblclick', 'contextmenu', 'input', 'select', 'check', 'keypress', 'scroll', 'page', 'close', 'unsupported'}


def problem(code: str, message: str, path: str = '', severity: str = 'error') -> dict[str, Any]:
    return {'code': code, 'message': message, 'path': path.split('.') if path else [], 'severity': severity}


def generate(recording_id: str, generation_id: str, steps: list[dict[str, Any]], target: dict[str, Any]) -> dict[str, Any]:
    """Pure conversion; this operation never writes or runs a workflow."""
    document, layout = target['document'], target['layout']
    validate_structure(document, layout)
    tail: str | None = None
    if document['nodes']:
        plan = compile_control(document, check_variables=False)
        last = plan[-1]
        last_node = next(n for n in document['nodes'] if n['id'] == last['nodeId'])
        tail = last.get('endNodeId') if last_node['type'] == 'condition' else last['nodeId']
    definitions = {d['type']: d for d in node_catalog()}
    aliases = {n['config'].get(f) for n in document['nodes'] for f in ('pageAlias', 'newPageAlias') if n['config'].get(f)}
    pages: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    mapping: dict[str, list[str]] = {}
    current: str | None = None

    def alias(page: str) -> str:
        if page not in pages:
            index = len(pages) + 1
            name = f'page_{index}'
            while name in aliases:
                index += 1
                name = f'page_{index}'
            aliases.add(name)
            pages[page] = name
        return pages[page]

    def add(step: dict[str, Any], kind: str, config: dict[str, Any]) -> dict[str, Any]:
        identifier = str(uuid5(NAMESPACE_URL, f'{recording_id}/{generation_id}/{step["stepId"]}/{len(nodes)}'))
        node = {'id': identifier, 'type': kind, 'label': step.get('label') or definitions[kind]['title'],
                'config': {**deepcopy(definitions[kind]['defaultConfig']), **config}}
        node['literalPaths'] = sorted(literal_eligible(node)) if not step.get('useVariables', False) else []
        previous = nodes[-1]['id'] if nodes else tail
        if previous:
            source = nodes[-1] if nodes else next(n for n in document['nodes'] if n['id'] == previous)
            edges.append({'id': str(uuid5(NAMESPACE_URL, identifier + '/edge')), 'source': previous, 'target': identifier,
                          'sourceHandle': 'done' if source['type'] == 'loop' else 'out', 'targetHandle': 'in'})
        nodes.append(node)
        mapping.setdefault(step['stepId'], []).append(identifier)
        return node

    bound: set[str] = set()
    for step in steps:
        if step.get('excluded'):
            continue
        c = deepcopy(step['config'])
        action, page = step['action'], step['pageId']
        for issue in step.get('issues', []):
            issues.append({**issue, 'stepId': step['stepId']})
        if action == 'unsupported':
            issues.append({**problem('RECORDING_UNSUPPORTED', '此操作尚不能生成，请补充支持动作或明确排除'), 'stepId': step['stepId']})
            continue
        if action == 'navigate':
            mode = c.get('navigation', 'unconfirmed')
            if mode == 'unconfirmed':
                issues.append({**problem('NAVIGATION_UNCONFIRMED', '请确认主动导航或前一步的导航结果', 'config.navigation'), 'stepId': step['stepId']})
                continue
            if mode == 'direct':
                add(step, 'open_page', {'url': c['url'], 'openMode': 'new_tab' if page not in bound else 'current_tab', 'pageAlias': alias(page)})
                bound.add(page)
            else:
                if page not in bound:
                    cause = c.get('causeStepId')
                    source = next((n for n in reversed(nodes) if n['id'] in mapping.get(cause, []) and n['type'] in {'click_element', 'press_key'}), None)
                    if source is None:
                        issues.append({**problem('PAGE_SOURCE_REQUIRED', '请指定打开此页面的点击或按键步骤', 'config.causeStepId'), 'stepId': step['stepId']})
                        continue
                    source['config'].update(followNewTab=True, newPageAlias=alias(page))
                    bound.add(page)
                elif current != page:
                    add(step, 'switch_page', {'pageAlias': alias(page)})
                add(step, 'wait_page', {'url': c['url']})
            current = page
            continue
        if page not in bound:
            issues.append({**problem('PAGE_SOURCE_REQUIRED', '页面缺少录入的起始导航或弹窗来源'), 'stepId': step['stepId']})
            continue
        if current != page:
            add(step, 'switch_page', {'pageAlias': alias(page)})
            current = page
        target_config = {k: c[k] for k in ('selector', 'framePath') if k in c}
        if action in {'click', 'dblclick', 'contextmenu'}:
            add(step, 'click_element', {**target_config, 'clickType': {'click': 'single', 'dblclick': 'double', 'contextmenu': 'right'}[action]})
        elif action == 'input':
            add(step, 'input_text', {**target_config, 'text': c.get('text', ''), 'requiresValue': c.get('requiresValue', False), 'inputMode': c.get('inputMode', 'fill')})
        elif action == 'select':
            add(step, 'select_option', {**target_config, 'values': c['values']})
        elif action == 'check':
            add(step, 'set_checked', {**target_config, 'checked': c['checked']})
        elif action == 'keypress':
            add(step, 'press_key', {**target_config, 'key': c['key']})
        elif action == 'scroll':
            add(step, 'scroll_page', {**target_config, **{k: c[k] for k in ('target', 'x', 'y')}})
        elif action == 'close':
            add(step, 'close_page', {'pageAlias': alias(page)})
            bound.remove(page)
            current = None
        elif action == 'page':
            add(step, 'switch_page', {'pageAlias': alias(page)})
    if len(document['nodes']) + len(nodes) > 2000:
        raise WorkflowError('RECORDING_GRAPH_LIMIT', '工作流最多2000个节点，请分段生成', 422)
    if not nodes and not issues:
        raise WorkflowError('RECORDING_EMPTY', '没有可以加入的步骤', 422)
    return {'generationId': generation_id, 'nodes': nodes, 'edges': edges, 'variables': [], 'issues': issues, 'mapping': mapping, 'aliases': pages}
