from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from autoflow.application.workflows.executors.workflow_chain import (
    RunWorkflowFileExecutor,
)
from autoflow.domain.workflows.execution import (
    ExecutionContext,
    NestedWorkflowResult,
)


class FakeNested:
    def __init__(self, result: NestedWorkflowResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any], bool]] = []

    async def run_workflow(
        self,
        reference: str,
        *,
        variables: Mapping[str, Any],
        wait_complete: bool,
    ) -> NestedWorkflowResult:
        self.calls.append((reference, dict(variables), wait_complete))
        return self.result


@pytest.mark.asyncio
async def test_run_workflow_file_sync_transfers_variables_and_summary() -> None:
    nested = FakeNested(
        NestedWorkflowResult(
            "child.json", "子工作流", True, {"parent": 3, "child": 2}, 2, 0
        )
    )
    context = ExecutionContext(
        variables={"parent": 1, "childRef": "child.json"},
        nested_workflows=nested,
    )
    result = await RunWorkflowFileExecutor().execute(
        {
            "workflowFile": "{childRef}",
            "resultVariable": "summary",
        },
        context,
    )

    assert result.success is True
    assert nested.calls == [
        ("child.json", {"parent": 1, "childRef": "child.json"}, True)
    ]
    assert context.variables["child"] == 2
    assert context.variables["summary"] == result.data
    assert result.message == "工作流「子工作流」执行完成（2 个模块）"


@pytest.mark.asyncio
async def test_run_workflow_file_failure_can_continue_without_variable_transfer() -> None:
    nested = FakeNested(
        NestedWorkflowResult("child", "子工作流", False, {"child": 2}, 1, 1, "boom")
    )
    context = ExecutionContext(variables={"parent": 1}, nested_workflows=nested)
    result = await RunWorkflowFileExecutor().execute(
        {
            "workflowFile": "child",
            "passVariables": "false",
            "collectVariables": "false",
            "stopOnFail": "false",
        },
        context,
    )

    assert result.success is True
    assert "已按配置继续" in result.message
    assert nested.calls == [("child", {}, True)]
    assert context.variables == {"parent": 1}


@pytest.mark.asyncio
async def test_run_workflow_file_async_trigger_returns_immediately() -> None:
    nested = FakeNested(
        NestedWorkflowResult("child", "子工作流", True, {}, 0, 0, waited=False)
    )
    context = ExecutionContext(nested_workflows=nested)
    result = await RunWorkflowFileExecutor().execute(
        {"workflowFile": "child", "waitComplete": False}, context
    )

    assert result.data == {"workflow": "子工作流", "waited": False}
    assert nested.calls == [("child", {}, False)]
