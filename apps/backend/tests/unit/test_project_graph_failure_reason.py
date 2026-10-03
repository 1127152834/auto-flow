"""Remediation M1 R1-03/R1-05 through the project worker adapter."""

import pytest

from autoflow.providers.browser.project_graph import ProjectGraphExecutor


def node(identity, kind, **config):
    return {'id': identity, 'data': {'moduleType': kind, **config}}


@pytest.mark.asyncio
async def test_batch_failure_log_carries_the_executor_reason():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    document = {'nodes': [node('parse', 'json_parse', jsonString='{not json', variableName='parsed')], 'edges': []}
    result = await executor.run({'document': document})
    assert result['status'] == 'failed'
    assert result['error']['code'] == 'WORKFLOW_NODE_FAILED'
    assert result['error']['message'].startswith('工作流节点执行失败：')
    assert len(result['error']['message']) > len('工作流节点执行失败：')
    error_logs = [event[3]['message'] for event in events if event[0] == 'log' and event[3].get('level') == 'error']
    assert error_logs == [result['error']['message']]


def edge(source, target, handle=None):
    value = {'id': f'{source}-{target}', 'source': source, 'target': target}
    if handle:
        value['sourceHandle'] = handle
    return value


def caught_failure_document(**top_level):
    return {
        'nodes': [
            node('parse', 'json_parse', jsonString='{not json', variableName='parsed'),
            node('recover', 'set_variable', variableName='recovered', variableValue='yes'),
        ],
        'edges': [edge('parse', 'recover', 'error')],
        **top_level,
    }


async def run_document(document):
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    return await executor.run({'document': document}), events


@pytest.mark.asyncio
async def test_v2_failure_handled_by_the_error_branch_does_not_fail_the_batch_task():
    result, _ = await run_document(caught_failure_document(executionSemantics='autoflow-v2'))
    assert result['status'] == 'succeeded'
    assert result['error'] is None


@pytest.mark.asyncio
async def test_legacy_handled_failure_keeps_failing_the_batch_task():
    result, _ = await run_document(caught_failure_document())
    assert result['status'] == 'failed'
    assert result['error']['code'] == 'WORKFLOW_NODE_FAILED'


@pytest.mark.asyncio
async def test_inert_retry_settings_are_reported_once_per_node():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    document = {
        'nodes': [
            node('loop', 'loop', count=2, indexVariable='i'),
            node('set', 'set_variable', variableName='x', variableValue='{i}', label='赋值', retryCount=3, timeoutAction='skip'),
        ],
        'edges': [{'id': 'e', 'source': 'loop', 'target': 'set', 'sourceHandle': 'loop'}],
    }
    assert (await executor.run({'document': document}))['status'] == 'succeeded'
    warnings = [event[3]['message'] for event in events if event[0] == 'log' and event[3].get('level') == 'warning']
    assert warnings == ['「赋值」的以下设置尚未生效，运行时会被忽略：重试次数、运行超时后']


@pytest.mark.asyncio
async def test_whole_node_timeout_names_the_limit_instead_of_a_bare_headline():
    """R1-03: a timeout reads "工作流节点执行超时：<原因>", not only the headline."""
    document = {'nodes': [node('pause', 'wait', waitType='time', duration=5000, timeout=0.05)], 'edges': []}
    result, events = await run_document(document)
    assert result['status'] == 'failed'
    assert result['error']['code'] == 'WORKFLOW_NODE_TIMEOUT'
    assert result['error']['message'] == '工作流节点执行超时：节点在 0.05 秒内未完成'
    error_logs = [event[3]['message'] for event in events if event[0] == 'log' and event[3].get('level') == 'error']
    assert error_logs == [result['error']['message']]


@pytest.mark.asyncio
async def test_started_attempts_carry_the_side_effect_declaration():
    """R2-10: the acknowledged start fact says whether the node may act outside the run."""
    document = {
        'nodes': [
            node('calc', 'set_variable', variableName='x', variableValue='1'),
            node('act', 'run_command', command=''),
        ],
        'edges': [edge('calc', 'act')],
    }
    _, events = await run_document(document)
    started = {event[1]: event[3].get('sideEffect') for event in events if event[0] == 'nodeAttempt' and event[3].get('status') == 'started'}
    assert started == {'calc': 'none', 'act': 'possible'}
