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


@pytest.mark.asyncio
async def test_manual_declared_inputs_and_selected_successor_reach_same_live_context_once():
    executed = []
    async def emit(kind, node_id, _visit, payload):
        if kind == 'nodeAttempt' and payload['status'] == 'started': executed.append(node_id)
    async def request(*_args): return {'result': {'action': 'resume', 'inputs': {'code': '001'}, 'targetNodeId': 'chosen'}}
    executor = ProjectGraphExecutor(None, {}, emit, lambda: False, capability=request)
    document = {'nodes': [node('manual', 'project_manual', reason='code', inputSchema=[{'name': 'code', 'type': 'string', 'required': True}], resumeTargets=[{'nodeId': 'chosen'}, {'nodeId': 'other'}]), node('chosen', 'set_variable', variableName='answer', variableValue='code-{code}'), node('other', 'set_variable', variableName='answer', variableValue='wrong'), node('join', 'set_variable', variableName='joined', variableValue='{answer}')], 'edges': [{'source': 'manual', 'target': 'chosen'}, {'source': 'manual', 'target': 'other'}, {'source': 'chosen', 'target': 'join'}, {'source': 'other', 'target': 'join'}]}
    assert (await executor.run({'document': document}))['status'] == 'succeeded'
    assert executor.context.variables == {'code': '001', 'answer': 'code-001', 'joined': 'code-001'}
    assert executed == ['manual', 'chosen', 'join']


@pytest.mark.asyncio
async def test_structured_parallel_loops_keep_independent_frames_and_explicit_outputs():
    starts = []
    async def emit(kind, node_id, _visit, payload):
        await asyncio.sleep(.001)
        if kind == 'nodeAttempt' and payload['status'] == 'started': starts.append((node_id, payload['executionContext']))
    executor = ProjectGraphExecutor(None, {'index': 999, 'local': 'parent'}, emit, lambda: False)
    document = {'nodes': [node('fork', 'set_variable', variableName='started', variableValue='yes', parallel={'joinNodeId': 'join', 'outputs': {'a': {'local': 'aResult'}, 'b': {'local': 'bResult'}}}), node('a', 'loop', count=2, indexVariable='index'), node('a-body', 'set_variable', variableName='local', variableValue='A-{index}'), node('b', 'loop', count=3, indexVariable='index'), node('b-body', 'set_variable', variableName='local', variableValue='B-{index}'), node('join', 'set_variable', variableName='joined', variableValue='{aResult}/{bResult}')], 'edges': [{'source': 'fork', 'target': 'a'}, {'source': 'fork', 'target': 'b'}, {'source': 'a', 'target': 'a-body', 'sourceHandle': 'loop'}, {'source': 'a', 'target': 'join', 'sourceHandle': 'done'}, {'source': 'b', 'target': 'b-body', 'sourceHandle': 'loop'}, {'source': 'b', 'target': 'join', 'sourceHandle': 'done'}]}
    assert (await executor.run({'document': document}))['status'] == 'succeeded'
    assert [(n, c['loops'][0]['currentIndex']) for n, c in starts if n == 'a-body'] == [('a-body', 0), ('a-body', 1)]
    assert [(n, c['loops'][0]['currentIndex']) for n, c in starts if n == 'b-body'] == [('b-body', 0), ('b-body', 1), ('b-body', 2)]
    assert executor.context.variables == {'index': 999, 'local': 'parent', 'started': 'yes', 'aResult': 'A-1', 'bResult': 'B-2', 'joined': 'A-1/B-2'}
    assert sum(n == 'join' for n, _ in starts) == 1


@pytest.mark.asyncio
async def test_parallel_manual_queue_hands_off_before_ordinary_nodes_and_never_overlaps():
    actions = []
    active = False
    async def emit(*_args): await asyncio.sleep(0)
    async def request(node_id, _visit, operation, _arguments):
        nonlocal active
        if operation == 'manual':
            assert not active, 'only the owning manual checkpoint may be live'
            active = True; actions.append(node_id + '-start')
            await asyncio.sleep(.01)
            active = False; actions.append(node_id + '-end')
            return {'result': {'action': 'resume', 'inputs': {}}}
        assert not active, 'ordinary work must be quiescent while a manual item is live'
        actions.append(node_id)
        return {'result': {}}
    executor = ProjectGraphExecutor(None, {}, emit, lambda: False, capability=request)
    document = {'nodes': [node('fork', 'set_variable', variableName='start', variableValue='yes', parallel={'joinNodeId': 'join', 'outputs': {}}), node('manual-a', 'project_manual', reason='A'), node('manual-b', 'project_manual', reason='B'), node('normal-a', 'project_data', operation='inputs'), node('normal-b', 'project_data', operation='inputs'), node('join', 'set_variable', variableName='joined', variableValue='yes')], 'edges': [{'source': 'fork', 'target': 'manual-a'}, {'source': 'fork', 'target': 'manual-b'}, {'source': 'manual-a', 'target': 'normal-a'}, {'source': 'manual-b', 'target': 'normal-b'}, {'source': 'normal-a', 'target': 'join'}, {'source': 'normal-b', 'target': 'join'}]}
    assert (await executor.run({'document': document}))['status'] == 'succeeded'
    assert actions[:4] == ['manual-a-start', 'manual-a-end', 'manual-b-start', 'manual-b-end']
    assert sorted(actions[4:]) == ['normal-a', 'normal-b']


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['resume', 'finish', 'cancel'])
async def test_parallel_manual_waits_for_inflight_work_and_discards_queue_on_stop(outcome):
    actions = []
    inflight = asyncio.Event()
    release = asyncio.Event()
    stopped = False
    async def emit(*_args): await asyncio.sleep(0)
    async def request(node_id, _visit, operation, _arguments):
        nonlocal stopped
        if operation == 'inputs':
            actions.append('work-start'); inflight.set()
            await release.wait()
            actions.append('work-end')
            return {'result': {}}
        assert actions[:2] == ['work-start', 'work-end'], 'checkpoint must wait for already running work'
        actions.append(node_id)
        if outcome == 'cancel':
            stopped = True
            await asyncio.sleep(.1)
        if outcome == 'finish':
            return {'result': {'action': 'finish', 'outcome': 'succeeded', 'complete': True}}
        return {'result': {'action': 'resume', 'inputs': {}}}
    executor = ProjectGraphExecutor(None, {}, emit, lambda: stopped, capability=request)
    document = {'nodes': [node('fork', 'set_variable', variableName='start', variableValue='yes', parallel={'joinNodeId': 'join', 'outputs': {}}), node('work', 'project_data', operation='inputs'), node('manual-a', 'project_manual', reason='A'), node('manual-b', 'project_manual', reason='B'), node('join', 'set_variable', variableName='joined', variableValue='yes')], 'edges': [{'source': 'fork', 'target': identity} for identity in ['work', 'manual-a', 'manual-b']] + [{'source': identity, 'target': 'join'} for identity in ['work', 'manual-a', 'manual-b']]}
    running = asyncio.create_task(executor.run({'document': document}))
    await asyncio.wait_for(inflight.wait(), 1)
    await asyncio.sleep(.02)
    assert actions == ['work-start']
    release.set()
    if outcome == 'cancel':
        with pytest.raises(asyncio.CancelledError): await asyncio.wait_for(running, 2)
    else:
        assert (await asyncio.wait_for(running, 2))['status'] == 'succeeded'
    assert actions == ['work-start', 'work-end', 'manual-a'] + (['manual-b'] if outcome == 'resume' else [])
    assert ('joined' in executor.context.variables) == (outcome == 'resume')


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['command', 'transport'])
async def test_parallel_failure_awaits_sibling_cleanup_without_exporting_partial_values(failure):
    committed = []
    running = asyncio.Event()
    cleaned = asyncio.Event()
    async def emit(*_args): pass
    async def request(node_id, _visit, _operation, _arguments):
        if node_id == 'write':
            committed.append('durable'); running.set()
            try: await asyncio.Event().wait()
            finally:
                await asyncio.sleep(.01)
                cleaned.set()
        await running.wait()
        if failure == 'transport': raise RuntimeError('later branch failed')
        return {'error': {'code': 'LATER_BRANCH_FAILED'}}
    executor = ProjectGraphExecutor(None, {'answer': 'parent'}, emit, lambda: False, capability=request)
    document = {'nodes': [node('fork', 'set_variable', variableName='start', variableValue='yes', parallel={'joinNodeId': 'join', 'outputs': {'write': {'saved': 'answer'}}}), node('write', 'project_data', operation='inputs', variableName='saved'), node('fail', 'project_data', operation='inputs'), node('join', 'set_variable', variableName='joined', variableValue='yes')], 'edges': [{'source': 'fork', 'target': identity} for identity in ['write', 'fail']] + [{'source': identity, 'target': 'join'} for identity in ['write', 'fail']]}
    if failure == 'transport':
        with pytest.raises(RuntimeError, match='later branch failed'): await asyncio.wait_for(executor.run({'document': document}), 2)
    else:
        assert (await asyncio.wait_for(executor.run({'document': document}), 2))['status'] == 'failed'
    assert committed == ['durable'] and cleaned.is_set()
    assert executor.context.variables == {'answer': 'parent', 'start': 'yes'}


@pytest.mark.asyncio
async def test_parallel_local_break_inside_outer_loop_and_subflow_stays_in_its_branch():
    starts = []
    async def emit(kind, identity, _visit, payload):
        await asyncio.sleep(0)
        if kind == 'nodeAttempt' and payload['status'] == 'started': starts.append((identity, payload['executionContext']))
    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    document = {'nodes': [
        node('outer', 'loop', count=2, indexVariable='outerIndex'),
        node('fork', 'set_variable', variableName='start', variableValue='yes', parallel={'joinNodeId': 'join', 'outputs': {'left': {'local': 'a'}, 'right': {'local': 'b'}}}),
        node('left', 'loop', count=5, indexVariable='index'),
        node('left-value', 'set_variable', variableName='local', variableValue='A-{outerIndex}-{index}'), node('break', 'break_loop'),
        node('right', 'loop', count=3, indexVariable='index'),
        node('call', 'subflow', subflowGroupId='child', inputs={'value': 'B-{outerIndex}-{index}'}, outputs={'answer': 'local'}),
        node('child', 'subflow_header'), node('child-value', 'set_variable', variableName='answer', variableValue='{value}'),
        node('join', 'set_variable', variableName='joined', variableValue='{a}/{b}'),
        node('done', 'set_variable', variableName='finished', variableValue='yes'),
    ], 'edges': [{'source': a, 'target': b, **({'sourceHandle': handle} if handle else {})} for a, b, handle in [('outer', 'fork', 'loop'), ('outer', 'done', 'done'), ('fork', 'left', None), ('fork', 'right', None), ('left', 'left-value', 'loop'), ('left-value', 'break', None), ('left', 'join', 'done'), ('right', 'call', 'loop'), ('right', 'join', 'done'), ('child', 'child-value', None)]]}
    assert (await executor.run({'document': document}))['status'] == 'succeeded'
    assert executor.context.variables['joined'] == 'A-1-0/B-1-2'
    assert sum(n == 'left-value' for n, _ in starts) == 2
    assert sum(n == 'child-value' for n, _ in starts) == 6
    assert sum(n == 'join' for n, _ in starts) == 2
    assert sum(n == 'done' for n, _ in starts) == 1
    assert all([scope['kind'] for scope in c['scopes']] == ['parallel', 'subflow'] for n, c in starts if n == 'child-value')
    assert 'local' not in executor.context.variables and 'index' not in executor.context.variables
