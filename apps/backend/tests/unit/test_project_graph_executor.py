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
