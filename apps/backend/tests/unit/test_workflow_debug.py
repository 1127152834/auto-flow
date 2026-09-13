import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from autoflow.application.workflows.debug import WorkflowDebug
from autoflow.application.workflows.execution import WorkflowExecution
from autoflow.domain.workflows.debug import prepare_debug
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from tests.fixtures.workflow_control import (
    accumulating_loop,
    literal,
    node,
    payload,
    variable,
)


async def until(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(.001)


def runner(tmp_path, body, options=None):
    prepared = prepare_debug(**body, options=options or {'start': 'entry'})
    values, events = deepcopy(prepared.variables), []
    async def action(*_):
        raise ValueError('controlled failure')
    def error(error, identifier):
        return {'code': 'TEST_ERROR', 'nodeId': identifier, 'path': [], 'message': str(error)}
    debug = WorkflowDebug(prepared.debug, values, events.append, WorkflowArtifacts(tmp_path, 'run').save_json, action)
    execution = WorkflowExecution(values, events.append, action, action, error, debug)
    task = asyncio.create_task(execution.run(prepared.document, prepared.plan))
    return debug, task, events


async def command(debug, action, **extra):
    return await debug.command({'commandId': uuid4().hex, 'expectedRevision': debug.revision, 'pauseId': debug.pause_id, 'action': action, **extra})


@pytest.mark.asyncio
async def test_single_step_identity_and_loop_local_protection(tmp_path):
    debug, task, events = runner(tmp_path, accumulating_loop())
    try:
        await until(lambda: debug.state == 'paused')
        assert not [e for e in events if e['type'] == 'node_started']
        old = debug.pause_id
        request = {'commandId': 'stable', 'expectedRevision': debug.revision, 'pauseId': old, 'action': 'step'}
        assert (await debug.command(request))['state'] == 'applied'
        await until(lambda: debug.pause_id and debug.pause_id != old)
        assert len([e for e in events if e['type'] == 'node_started']) == 1
        assert debug.variables['index'] == 1 and debug.scopes['index'] == 'loop'
        assert (await debug.command(request))['state'] == 'applied'
        await asyncio.sleep(.02)
        assert len([e for e in events if e['type'] == 'node_started']) == 1
        result = await command(debug, 'variables', values={'result': [9], 'index': 7})
        assert result['state'] == 'rejected' and debug.variables['result'] == []
        assert (await command(debug, 'variables', values={'result': [9]}))['state'] == 'applied'
        await command(debug, 'resume')
        assert (await task)['state'] == 'succeeded'
        assert debug.variables['result'] == [9, 1, 3]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_pause_excludes_node_timeout_and_failure_is_readonly(tmp_path):
    body = payload([node('a', 'set_variable', variableName='x', value=literal(1), timeoutSeconds=.01), node('b', 'click_element', selector='#missing')], [('a','out','b')])
    debug, task, events = runner(tmp_path, body)
    try:
        await until(lambda: debug.state == 'paused')
        await asyncio.sleep(.04)
        await command(debug, 'resume')
        await until(lambda: debug.state == 'failed_paused')
        assert debug.variables['x'] == 1 and not task.done()
        assert (await command(debug, 'resume'))['state'] == 'rejected'
        assert (await command(debug, 'variables', values={'x': 3}))['state'] == 'rejected'
        assert len([e for e in events if e['type'] == 'node_failed']) == 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_direct_entry_validates_suffix_and_rejects_nested_entry():
    body = payload([node('bad', 'input_text', selector=''), node('use', 'set_variable', variableName='answer', value=variable('provided'))], [('bad','out','use')])
    result = prepare_debug(**body, options={'start': 'node', 'targetNodeId': 'use', 'values': {'provided': 42}})
    assert result.node_ids == ['use'] and result.variables == {'provided':42}
    with pytest.raises(WorkflowError):
        prepare_debug(**body, options={'start': 'entry'})
    with pytest.raises(WorkflowError, match='顶层'):
        prepare_debug(**accumulating_loop(), options={'start': 'node', 'targetNodeId':'append'})


@pytest.mark.asyncio
async def test_until_target_not_taken_does_not_force_branch(tmp_path):
    from tests.fixtures.workflow_control import rule
    body = payload([node('condition','condition',endNodeId='end',rules=[rule(literal(False))]), node('target','set_variable',variableName='bad',value=literal(True)),node('end','condition_end',ownerNodeId='condition')], [('condition','true','target'),('target','out','end'),('condition','false','end')])
    debug, task, events = runner(tmp_path,body,{'start':'until','targetNodeId':'target'})
    assert (await task)['state'] == 'succeeded'
    assert 'bad' not in debug.variables
    assert any(e['message']=='本次路径未到达目标节点' for e in events)


@pytest.mark.asyncio
async def test_1000_appends_record_increment_not_entire_list(tmp_path):
    import json
    body = payload([node('loop','loop',source=literal(1000),endNodeId='end'),node('append','set_variable',variableName='items',operation='append',value=variable('index')),node('end','loop_end',ownerNodeId='loop')],[('loop','body','append'),('append','out','end')],[{'name':'items','type':'array','value':[]}])
    debug, task, _events = runner(tmp_path, body)
    await until(lambda: debug.state=='paused')
    await command(debug,'resume')
    assert (await task)['state']=='succeeded'
    assert debug.variables['items']==list(range(1,1001))
    deltas=[json.loads(p.read_text()) for p in (tmp_path/'run'/'artifacts').glob('*.json') if '"operation":"append"' in p.read_text()]
    assert len(deltas)==1000
    assert all(type(d['changes'][0]['value']) is int for d in deltas)
    assert sum(len(json.dumps(d)) for d in deltas)<400000


@pytest.mark.parametrize('field,value', [('endNodeId',[]),('indexVariable',[]),('mode',{})])
def test_malformed_control_structure_returns_located_issue(field,value):
    body=accumulating_loop()
    body['document']['nodes'][0]['config'][field]=value
    with pytest.raises(WorkflowError) as caught:
        prepare_debug(**body,options={'start':'entry'})
    assert caught.value.issues[0].node_id=='loop'
    assert caught.value.issues[0].path==['config',field]


@pytest.mark.asyncio
async def test_failed_diagnostic_write_does_not_apply_variable_patch(tmp_path):
    debug,task,_events=runner(tmp_path,accumulating_loop())
    try:
        await until(lambda:debug.state=='paused')
        def failed_record(*_): raise OSError('disk full')
        debug.record=failed_record
        response=await command(debug,'variables',values={'result':[9],'new':True})
        assert response['state']=='rejected'
        assert debug.variables=={'result':[]}
    finally:
        task.cancel();await asyncio.gather(task,return_exceptions=True)
