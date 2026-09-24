import asyncio
from time import monotonic

import pytest
from autoflow.providers.browser.project_graph import ProjectGraphExecutor


def node(identity, kind, **config):
    return {'id': identity, 'data': {'moduleType': kind, **config}}


@pytest.mark.asyncio
async def test_project_adapter_uses_graph_branches_and_preserves_visit_events():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {'value': 2}, emit, lambda: False)
    document = {
        'nodes': [node('condition', 'condition', leftValue='{value}', rightValue=2),
                  node('yes', 'set_variable', variableName='answer', variableValue='selected'),
                  node('no', 'set_variable', variableName='answer', variableValue='wrong')],
        'edges': [{'id': 'yes', 'source': 'condition', 'target': 'yes', 'sourceHandle': 'true'},
                  {'id': 'no', 'source': 'condition', 'target': 'no', 'sourceHandle': 'false'}],
    }
    assert await executor.run({'document': document}) == {'status': 'succeeded', 'error': None}
    assert executor.context.variables['answer'] == 'selected'
    starts = [event for event in events if event[0] == 'nodeAttempt' and event[3]['status'] == 'started']
    assert [event[1] for event in starts] == ['condition', 'yes']
    assert len({event[2] for event in starts}) == 2


@pytest.mark.asyncio
async def test_committed_start_is_required_before_node_side_effect():
    async def reject(*_event):
        raise RuntimeError('database commit failed')

    executor = ProjectGraphExecutor(None, {}, reject, lambda: False)
    with pytest.raises(RuntimeError, match='commit failed'):
        await executor.run({'document': {'nodes': [node('set', 'set_variable', variableName='answer', variableValue=5)], 'edges': []}})
    assert 'answer' not in executor.context.variables


@pytest.mark.asyncio
async def test_stop_at_committed_start_prevents_first_node():
    stopped = False
    events = []

    async def stop(*event):
        nonlocal stopped
        events.append(event)
        stopped = True

    executor = ProjectGraphExecutor(None, {}, stop, lambda: stopped)
    with pytest.raises(asyncio.CancelledError):
        await executor.run({'document': {'nodes': [node('set', 'set_variable', variableName='answer', variableValue=5)], 'edges': []}})
    assert len(events) == 1 and 'answer' not in executor.context.variables


@pytest.mark.asyncio
async def test_switch_tab_outputs_each_variable_without_publishing_sensitive_url():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    executor.nodes = {
        'switch': {'moduleType': 'switch_tab', 'config': {
            'saveIndexVariable': 'index', 'saveTitleVariable': 'title',
            'saveUrlVariable': 'url',
        }}
    }
    executor.context.set_variable('index', 1)
    executor.context.set_variable('title', '受控页面')
    executor.context.set_variable('url', 'https://example.test/?token=secret', sensitive=True)
    executor.started['visit'] = monotonic()

    await executor.publish({
        'type': 'execution:node_complete', 'nodeId': 'switch',
        'executionId': 'visit', 'success': True,
        'data': {'index': 1, 'title': '受控页面', 'url': 'https://example.test/?token=[已隐藏]'},
    })

    assert [(payload['name'], payload['value']) for kind, _, _, payload in events if kind == 'output'] == [
        ('index', 1), ('title', '受控页面'),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('config,sensitive,expected', [
    ({}, False, ['new_element_selector', 'element_change_info']),
    ({'saveNewElementSelector': 'selector', 'saveChangeInfo': 'change'}, False, ['selector', 'change']),
    ({'saveNewElementSelector': '', 'saveChangeInfo': ''}, False, []),
    ({}, True, ['new_element_selector']),
])
async def test_element_change_outputs_preserve_disabled_and_sensitive_fields(config, sensitive, expected):
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    executor.nodes = {'observe': {'moduleType': 'element_change_trigger', 'config': config}}
    for name in ('new_element_selector', 'selector'):
        executor.context.set_variable(name, '#added')
    for name in ('element_change_info', 'change'):
        executor.context.set_variable(name, {'addedCount': 1}, sensitive=sensitive)
    executor.started['visit'] = monotonic()
    await executor.publish({
        'type': 'execution:node_complete', 'nodeId': 'observe',
        'executionId': 'visit', 'success': True,
        'data': {'newElementSelector': '#added', 'addedCount': 1},
    })
    assert [payload['name'] for kind, _, _, payload in events if kind == 'output'] == expected


@pytest.mark.asyncio
async def test_nested_failure_can_continue_without_failing_project_task():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    result = await executor.run({
        'document': {
            'nodes': [
                node('call', 'run_workflow_file', workflowFile='child', stopOnFail=False,
                     resultVariable='summary'),
                node('tail', 'set_variable', variableName='continued', variableValue='1'),
            ],
            'edges': [{'id': 'next', 'source': 'call', 'target': 'tail'}],
        },
        'workflowDependencies': {
            'child': {
                'id': 'child', 'name': '子工作流', 'variables': [],
                'nodes': [node('bad', 'set_variable', variableName='', variableValue='1')],
                'edges': [],
            },
        },
    })
    assert result == {'status': 'succeeded', 'error': None}
    assert executor.context.variables['continued'] == 1
    assert executor.context.variables['summary']['success'] is False
    assert any(kind == 'nodeAttempt' and node_id == 'bad' and payload['status'] == 'failed'
               for kind, node_id, _visit, payload in events)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,config,name', [
    ('face_recognition', {}, 'face_match_result'),
    ('image_ocr', {}, 'ocr_text'),
    ('face_recognition', {'resultVariable': ''}, None),
    ('image_ocr', {'resultVariable': ''}, None),
    ('ocr_captcha', {'variableName': ' primary ', 'resultVariable': 'alias'}, 'primary'),
    ('ocr_captcha', {'resultVariable': ' alias '}, 'alias'),
    ('ocr_captcha', {}, None),
])
@pytest.mark.parametrize('sensitive', [False, True])
async def test_recognition_project_outputs_use_actual_variables_and_source_names(kind, config, name, sensitive):
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    executor.nodes = {'recognition': {'moduleType': kind, 'config': config}}
    if name:
        executor.context.set_variable(name, 'actual value', sensitive=sensitive)
    executor.started['visit'] = monotonic()
    await executor.publish({
        'type': 'execution:node_complete', 'nodeId': 'recognition',
        'executionId': 'visit', 'success': True, 'data': {'text': 'different result envelope'},
    })
    outputs = [payload for kind, _, _, payload in events if kind == 'output']
    assert outputs == ([{'name': name, 'value': 'actual value'}] if name and not sensitive else [])


@pytest.mark.asyncio
@pytest.mark.parametrize('config,name', [({}, 'webhook_data'), ({'saveToVariable': 'request'}, 'request'), ({'saveToVariable': ''}, '')])
@pytest.mark.parametrize('sensitive', [False, True])
async def test_webhook_project_output_preserves_name_and_sensitive_boundary(config, name, sensitive):
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    executor.nodes = {'hook': {'moduleType': 'webhook_trigger', 'config': config}}
    value = {'body': {'answer': 42}}
    if name:
        executor.context.set_variable(name, value, sensitive=sensitive)
    executor.started['visit'] = monotonic()
    await executor.publish({
        'type': 'execution:node_complete', 'nodeId': 'hook', 'executionId': 'visit',
        'success': True, 'data': {'body': {'answer': 'not the current variable'}},
    })
    assert [payload for kind, _, _, payload in events if kind == 'output'] == (
        [{'name': name, 'value': value}] if name and not sensitive else []
    )
