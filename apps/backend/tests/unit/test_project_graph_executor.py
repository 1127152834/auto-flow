import asyncio

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
async def test_project_capability_preserves_typed_reference_uuid_and_leading_zero():
    from uuid import uuid4
    parameter = str(uuid4())
    reference = {'projectId': str(uuid4()), 'recordKey': {'type': 'text', 'value': '001'}}
    calls = []
    async def emit(*_event): pass
    async def request(node_id, visit, operation, arguments):
        calls.append((node_id, visit, operation, arguments))
        return {'result': {'saved': True}}
    executor = ProjectGraphExecutor(None, {'row': reference, parameter: 7, 'code': '001'}, emit, lambda: False, capability=request)
    document = {'nodes': [node('write', 'project_data', operation='updateRecord', variableName='saved', arguments={'recordRef': '{row}', 'expectedContentRevision': '{'+parameter+'}', 'values': {'code': '{code}'}})], 'edges': []}
    result = await executor.run({'document': document})
    assert result['status'] == 'succeeded'
    assert calls[0][3] == {'recordRef': reference, 'expectedContentRevision': 7, 'values': {'code': '001'}}


@pytest.mark.asyncio
async def test_end_requires_confirmed_retention_before_graph_success():
    async def emit(*_event): pass
    async def request(_node_id, _visit, operation, arguments):
        assert operation == 'end'
        assert arguments == {'retainEnvironment': {'enabled': True, 'mode': 'saveAs', 'name': '保留登录'}}
        return {'result': {'phase': 'saved_unlinked', 'complete': False}}
    executor = ProjectGraphExecutor(None, {}, emit, lambda: False, capability=request)
    result = await executor.run({'document': {'nodes': [node('end', 'project_end', retainEnvironment={'enabled': True, 'mode': 'saveAs', 'name': '保留登录'})], 'edges': []}})
    assert result['status'] == 'failed'
    assert result['error']['code'] == 'WORKFLOW_NODE_FAILED'


@pytest.mark.asyncio
async def test_manual_resume_continues_once_and_finish_skips_successors():
    for action in ('resume', 'finish'):
        calls = []
        async def emit(*_event): pass
        async def request(_node, _visit, operation, arguments, calls=calls, action=action):
            calls.append(operation)
            return {'result': {'action': action, 'inputs': {'answer': 'verified'}, 'outcome': 'succeeded', 'complete': True}}
        executor = ProjectGraphExecutor(None, {}, emit, lambda: False, capability=request)
        result = await executor.run({'document': {'nodes': [
            node('before', 'set_variable', variableName='before', variableValue='done'),
            node('manual', 'project_manual', reason='确认登录', timeoutSeconds=30, variableName='manual'),
            node('after', 'set_variable', variableName='after', variableValue='done'),
        ], 'edges': [{'source': 'before', 'target': 'manual'}, {'source': 'manual', 'target': 'after'}]}})
        assert result['status'] == 'succeeded'
        assert executor.context.variables['before'] == 'done'
        assert ('after' in executor.context.variables) == (action == 'resume')
        assert calls == ['manual']


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['succeeded', 'failed', 'timed_out'])
async def test_manual_finish_stops_remaining_loop_iterations_and_done(outcome):
    calls = []
    async def emit(*_event):
        await asyncio.sleep(0)
    async def request(node_id, *_args):
        calls.append(node_id)
        return {'result': {'action': 'finish', 'outcome': outcome, 'complete': True}}
    executor = ProjectGraphExecutor(None, {}, emit, lambda: False, capability=request)
    result = await executor.run({'document': {'nodes': [node('loop', 'loop', count=3), node('manual', 'project_manual', reason='stop'), node('end', 'project_end')], 'edges': [{'source': 'loop', 'target': 'manual', 'sourceHandle': 'loop'}, {'source': 'loop', 'target': 'end', 'sourceHandle': 'done'}]}})
    assert calls == ['manual']
    assert result['status'] == outcome


@pytest.mark.asyncio
async def test_end_join_waits_for_entire_loop():
    calls = []
    async def emit(*_event):
        await asyncio.sleep(0)
    async def request(node_id, *_args):
        await asyncio.sleep(.001)
        calls.append(node_id)
        return {'result': {'complete': True, 'phase': 'completed'}}
    executor = ProjectGraphExecutor(None, {}, emit, lambda: False, capability=request)
    result = await executor.run({'document': {'nodes': [node('loop', 'loop', count=2), node('body', 'project_data', operation='inputs'), node('other', 'set_variable', variableName='x', variableValue='1'), node('end', 'project_end')], 'edges': [{'source': 'loop', 'target': 'body', 'sourceHandle': 'loop'}, {'source': 'loop', 'target': 'end', 'sourceHandle': 'done'}, {'source': 'other', 'target': 'end'}]}})
    assert result['status'] == 'succeeded', (result, calls)
    assert calls == ['body', 'body', 'end']


@pytest.mark.asyncio
async def test_browser_action_resolves_nested_reference_exactly_once():
    from unittest.mock import AsyncMock, Mock
    locator = Mock()
    locator.first = locator
    locator.fill = AsyncMock()
    page = Mock()
    page.is_closed.return_value = False
    page.locator.return_value = locator
    async def emit(*_args): pass
    executor = ProjectGraphExecutor(None, {'record': {'name': '001-{literal}'}}, emit, lambda: False)
    executor.legacy.page = page
    result = await executor.run({'document': {'nodes': [node('input', 'input_text', selector='#name', text="{record['name']}", clearBefore=True)], 'edges': []}})
    assert result['status'] == 'succeeded'
    locator.fill.assert_awaited_once_with('001-{literal}')


@pytest.mark.asyncio
async def test_frozen_subflow_twice_isolates_inputs_and_exports_only_declared_outputs():
    events = []
    async def emit(*event): events.append(event)
    document = {'nodes': [
        node('first', 'subflow', subflowGroupId='child', inputs={'value': 'first'}, outputs={'answer': 'firstAnswer'}),
        node('second', 'subflow', subflowGroupId='child', inputs={'value': 'second'}, outputs={'answer': 'secondAnswer'}),
        node('child', 'subflow_header', subflowName='child'),
        node('write', 'set_variable', variableName='answer', variableValue='{value}'),
        node('private', 'set_variable', variableName='private', variableValue='child only'),
    ], 'edges': [{'source': 'first', 'target': 'second'}, {'source': 'child', 'target': 'write'}, {'source': 'write', 'target': 'private'}]}
    executor = ProjectGraphExecutor(None, {'answer': 'parent', 'private': 'parent'}, emit, lambda: False)
    assert (await executor.run({'document': document}))['status'] == 'succeeded'
    assert executor.context.variables == {'answer': 'parent', 'private': 'parent', 'firstAnswer': 'first', 'secondAnswer': 'second'}
    starts = [e for e in events if e[0] == 'nodeAttempt' and e[3]['status'] == 'started']
    writes = [e for e in starts if e[1] == 'write']
    assert len(writes) == 2 and writes[0][2] != writes[1][2]
    assert [e[3]['executionContext']['scopes'][0]['callNodeId'] for e in writes] == ['first', 'second']


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['node', 'missing-output', 'cancel'])
async def test_subflow_failure_or_cancel_never_exports_partial_variables(failure):
    stopped = False
    async def emit(kind, node_id, _visit, payload):
        nonlocal stopped
        if failure == 'cancel' and node_id == 'write' and kind == 'nodeAttempt' and payload['status'] == 'started':
            stopped = True
    executor = ProjectGraphExecutor(None, {'answer': 'unchanged'}, emit, lambda: stopped)
    nodes = [node('call', 'subflow', subflowGroupId='child', inputs={}, outputs={'missing' if failure == 'missing-output' else 'value': 'answer'}), node('child', 'subflow_header'), node('write', 'set_variable', variableName='value', variableValue='partial')]
    edges = [{'source': 'child', 'target': 'write'}]
    if failure == 'node':
        nodes.append(node('fail', 'subflow', subflowGroupId='absent', inputs={}, outputs={}))
        edges.append({'source': 'write', 'target': 'fail'})
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError): await executor.run({'document': {'nodes': nodes, 'edges': edges}})
    else:
        assert (await executor.run({'document': {'nodes': nodes, 'edges': edges}}))['status'] == 'failed'
    assert executor.context.variables == {'answer': 'unchanged'}
