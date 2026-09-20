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
