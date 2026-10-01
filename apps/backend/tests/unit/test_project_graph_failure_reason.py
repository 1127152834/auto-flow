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
