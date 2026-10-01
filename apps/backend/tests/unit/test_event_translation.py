"""Remediation M1 R1-03: both execution paths word a node failure the same way."""

import pytest

from autoflow.application.workflows import runtime
from autoflow.application.workflows.event_translation import (
    MAX_REASON_CHARS,
    NODE_TIMEOUT_CODE,
    SENSITIVE_FAILURE_REASON,
    failure_reason,
    node_failure_message,
)
from autoflow.application.workflows.executors.base import ModuleResult
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.project_graph import ProjectGraphExecutor


def test_reason_is_trimmed_bounded_and_never_the_bare_timeout_code():
    assert failure_reason("  boom \n") == "boom"
    assert failure_reason(NODE_TIMEOUT_CODE) == ""
    assert failure_reason(None) == ""
    assert failure_reason("x" * (MAX_REASON_CHARS + 5)) == "x" * MAX_REASON_CHARS + "…"
    assert node_failure_message(NODE_TIMEOUT_CODE, timeout=True) == "工作流节点执行超时"
    assert node_failure_message("页面没有响应", timeout=False) == "工作流节点执行失败：页面没有响应"


def test_a_credential_derived_error_is_replaced_by_the_same_text_the_batch_path_shows():
    context = ExecutionContext()
    context.mark_sensitive_use()
    reported = runtime._reported_result(ModuleResult(success=False, error="login failed for hunter2"), context)
    assert reported.error == SENSITIVE_FAILURE_REASON
    assert "hunter2" not in node_failure_message(reported.error, timeout=False)


@pytest.mark.asyncio
async def test_the_batch_graph_uses_the_shared_wording_for_a_real_failure():
    events = []

    async def emit(*event):
        events.append(event)

    document = {'nodes': [{'id': 'parse', 'data': {'moduleType': 'json_parse', 'jsonString': '{bad', 'variableName': 'p'}}], 'edges': []}
    result = await ProjectGraphExecutor(None, {}, emit, lambda: False).run({'document': document})
    reason = result['error']['message'].split('：', 1)[1]
    assert result['error']['message'] == node_failure_message(reason, timeout=False)
