import asyncio
from copy import deepcopy

import pytest

from autoflow.application.workflows.execution import WorkflowExecution
from autoflow.domain.workflows.control_values import compare, equal, value_of
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run
from autoflow.domain.workflows.validation import workflow_issues
from tests.fixtures.workflow_control import (
    accumulating_loop,
    literal,
    node,
    payload,
    rule,
    variable,
)


async def execute(body):
    prepared = prepare_run(**body)
    values, events = deepcopy(prepared.variables), []

    async def action(*_):
        raise AssertionError('unexpected browser action')

    def error_of(error, identifier):
        return {'nodeId': identifier, 'code': error.issues[0].code if isinstance(error, WorkflowError) else type(error).__name__, 'message': str(error), 'path': error.issues[0].path if isinstance(error, WorkflowError) else []}

    runner = WorkflowExecution(values, events.append, action, action, error_of)
    result = await runner.run(prepared.document, prepared.plan)
    return result, values, events


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['count', 'foreach'])
async def test_loop_continue_accumulation_and_distinct_executions(mode):
    result, values, events = await execute(accumulating_loop(mode))
    assert result['state'] == 'succeeded'
    assert values == {'result': [1, 3], 'finished': True}
    starts = [e for e in events if e['type'] == 'node_started']
    assert len({e['executionId'] for e in starts}) == len(starts)
    appends = [e for e in starts if e['nodeId'] == 'append']
    assert [e['loopPath'] for e in appends] == [[{'loopNodeId': 'loop', 'iteration': 1}], [{'loopNodeId': 'loop', 'iteration': 3}]]
    assert [e['executionId'] for e in starts] == [e['executionId'] for e in events if e['type'] == 'node_succeeded']


@pytest.mark.asyncio
async def test_while_rechecks_typed_values_and_limit():
    body = payload([node('loop', 'loop', endNodeId='end', mode='while', rules=[rule(variable('n'), 'lt', literal(3))]),
                    node('increment', 'set_variable', operation='add', variableName='n', value=literal(1)), node('end', 'loop_end', ownerNodeId='loop')],
                   [('loop', 'body', 'increment'), ('increment', 'out', 'end')], [{'name': 'n', 'type': 'number', 'value': 0}])
    result, values, _ = await execute(body)
    assert result['state'] == 'succeeded' and values['n'] == 3
    body['document']['nodes'][0]['config']['maxIterations'] = 2
    result, values, _ = await execute(body)
    assert result['error']['code'] == 'LOOP_LIMIT_EXCEEDED' and values['n'] == 2


@pytest.mark.asyncio
async def test_break_only_nearest_loop_and_snapshot_list():
    body = payload([node('outer', 'loop', endNodeId='outerEnd', mode='foreach', source=variable('items'), indexVariable='outerIndex', itemVariable='outerItem'),
        node('inner', 'loop', endNodeId='innerEnd', source=literal(3)), node('break', 'break_loop'), node('innerEnd', 'loop_end', ownerNodeId='inner'),
        node('append', 'set_variable', variableName='items', operation='append', value=literal(9)), node('outerEnd', 'loop_end', ownerNodeId='outer')],
        [('outer', 'body', 'inner'), ('inner', 'body', 'break'), ('inner', 'done', 'append'), ('append', 'out', 'outerEnd')], [{'name': 'items', 'type': 'array', 'value': [1, 2]}])
    result, values, events = await execute(body)
    assert result['state'] == 'succeeded' and values['items'] == [1, 2, 9, 9]
    assert len([e for e in events if e['type'] == 'node_started' and e['nodeId'] == 'break']) == 2


@pytest.mark.parametrize('mutation,code', [
    (lambda b: b['document']['nodes'][0]['config'].update(indexVariable='result'), 'LOOP_VARIABLE_CONFLICT'),
    (lambda b: b['document']['nodes'][-1]['config'].update(value=variable('item')), 'VARIABLE_NOT_AVAILABLE'),
    (lambda b: b['document']['nodes'][0]['config'].update(endNodeId='join'), 'BLOCK_PAIR_INVALID'),
    (lambda b: b['document']['edges'].append({'id': 'bad', 'source': 'end', 'sourceHandle': 'out', 'target': 'loop', 'targetHandle': 'in'}), 'INVALID_CONTROL_PORT'),
])
def test_invalid_control_before_execution(mutation, code):
    body = accumulating_loop()
    mutation(body)
    with pytest.raises(WorkflowError) as caught:
        prepare_run(**body)
    assert any(issue.code == code for issue in caught.value.issues)


def test_only_all_reaching_branches_define_variable():
    body = payload([node('c', 'condition', endNodeId='end'), node('set', 'set_variable', variableName='x', value=literal(7)),
                    node('end', 'condition_end', ownerNodeId='c'), node('use', 'set_variable', variableName='y', value=variable('x'))],
                   [('c', 'true', 'set'), ('c', 'false', 'end'), ('set', 'out', 'end'), ('end', 'out', 'use')])
    with pytest.raises(WorkflowError) as caught:
        prepare_run(**body)
    assert caught.value.issues[0].code == 'VARIABLE_NOT_AVAILABLE'
    assert caught.value.issues[0].node_id == 'use'


@pytest.mark.parametrize('value', [0, False, ' ', [0]])
def test_empty_and_equality_are_strict(value):
    assert not compare('empty', value, None, [], 'n')
    assert not equal(True, 1) and not equal('1', 1) and not equal([True], [1])
    assert equal({'x': [1, None]}, {'x': [1.0, None]})


def test_typed_literal_is_not_template_and_missing_path_fails():
    assert value_of(literal('{missing}'), {}, [], 'n') == '{missing}'
    with pytest.raises(WorkflowError):
        value_of(variable('x', 'missing'), {'x': {}}, ['config', 'value'], 'n')


@pytest.mark.asyncio
async def test_empty_loop_and_zero_count_never_enter_body():
    for value, mode in [(0, 'count'), ([], 'foreach')]:
        body = accumulating_loop(mode)
        body['document']['nodes'][0]['config']['source'] = literal(value)
        result, values, events = await execute(body)
        assert result['state'] == 'succeeded' and values['result'] == []
        assert not any(e.get('nodeId') == 'append' for e in events)


@pytest.mark.asyncio
async def test_pure_variable_loop_yields_for_cancellation():
    body = accumulating_loop('count')
    body['document']['nodes'][0]['config'].update(source=literal(100000), maxIterations=100000)
    task = asyncio.create_task(execute(body))
    await asyncio.sleep(.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_incomplete_control_can_produce_save_issues():
    body = accumulating_loop()
    body['document']['edges'] = []
    assert workflow_issues(body['document'])

@pytest.mark.parametrize('field,value', [('mode', []), ('maxIterations', {}), ('indexVariable', []), ('source', {'kind': []}), ('source', {'kind': 'literal', 'value': 1, 'valueType': []})])
def test_malformed_control_fields_return_located_issues_not_server_errors(field, value):
    content = accumulating_loop()
    content['document']['nodes'][0]['config'][field] = value
    with pytest.raises(WorkflowError) as failed:
        prepare_run(**content)
    assert failed.value.issues
    assert failed.value.issues[0].node_id == 'loop'


def test_block_nesting_limit_counts_blocks_not_plain_nodes():
    def nested(depth):
        nodes = [node(f'c{i}', 'condition', endNodeId=f'e{i}') for i in range(depth)] + [node(f'e{i}', 'condition_end', ownerNodeId=f'c{i}') for i in range(depth)]
        edges = []
        for i in range(depth):
            edges.extend([(f'c{i}', 'true', f'c{i+1}' if i+1 < depth else f'e{i}'), (f'c{i}', 'false', f'e{i}')])
            if i: edges.append((f'e{i}', 'out', f'e{i-1}'))
        return payload(nodes, edges)
    assert prepare_run(**nested(32)).plan
    with pytest.raises(WorkflowError) as caught:
        prepare_run(**nested(33))
    assert caught.value.issues[0].code == 'BLOCK_DEPTH_EXCEEDED'


@pytest.mark.asyncio
async def test_while_false_on_limit_boundary_succeeds_and_list_append_copies():
    body = payload([node('loop', 'loop', mode='while', endNodeId='end', maxIterations=2, rules=[rule(variable('n'), 'lt', literal(2))]),
        node('add', 'set_variable', variableName='n', operation='add', value=literal(1)),
        node('append', 'set_variable', variableName='values', operation='append', value=literal([1, 2])), node('end', 'loop_end', ownerNodeId='loop')],
        [('loop', 'body', 'add'), ('add', 'out', 'append'), ('append', 'out', 'end')], [{'name': 'n', 'type': 'number', 'value': 0}, {'name': 'values', 'type': 'array', 'value': []}])
    result, values, _ = await execute(body)
    assert result['state'] == 'succeeded' and values['values'] == [[1, 2], [1, 2]]
    values['values'][0].append(3)
    assert values['values'][1] == [1, 2]


@pytest.mark.asyncio
async def test_schedule_limit_also_bounds_nested_empty_loops():
    body = payload([node('loop', 'loop', endNodeId='end', source=literal(100000), maxIterations=100000), node('end', 'loop_end', ownerNodeId='loop')], [('loop', 'body', 'end')])
    prepared = prepare_run(**body)
    starts = 0
    def emit(event):
        nonlocal starts
        if event['type'] == 'node_started': starts += 1
    async def unused(*_): raise AssertionError('pure loop must not call browser')
    def error_of(error, identifier):
        return {'nodeId': identifier, 'code': error.issues[0].code, 'message': str(error), 'path': []}
    runner = WorkflowExecution({}, emit, unused, unused, error_of)
    result = await runner.run(prepared.document, prepared.plan)
    assert result['state'] == 'failed' and result['error']['code'] == 'EXECUTION_LIMIT_EXCEEDED'
    assert starts == 100000  # Reject before an extra node is scheduled.
