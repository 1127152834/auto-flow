from __future__ import annotations

from datetime import UTC, datetime

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext, WorkflowClock


@pytest.mark.asyncio
async def test_scheduled_task_reports_progress_and_uses_resolved_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(
        "autoflow.application.workflows.executors.timing_probability.asyncio.sleep",
        sleep,
    )
    progress: list[str] = []
    context = ExecutionContext(
        variables={"seconds": 61},
        progress=lambda message, _level: _append(progress, message),
        clock=WorkflowClock(lambda: datetime(2026, 1, 1, tzinfo=UTC)),
    )

    result = (
        await build_production_executor_registry()
        .get("scheduled_task")
        .execute({"scheduleType": "delay", "delaySeconds": "{seconds}"}, context)
    )

    assert result.success is True
    assert result.message == "延迟 1分1秒 完成，开始执行"
    assert waits == [61]
    assert progress == ["⏰ 延迟 1分1秒 后执行"]
    assert [item["message"] for item in context.log_records] == [
        "⏰ 延迟任务已设置",
        "⏳ 延迟时长: 1分1秒",
    ]


async def _append(values: list[str], value: str) -> None:
    values.append(value)


@pytest.mark.asyncio
async def test_probability_branch_routes_only_the_selected_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "autoflow.application.workflows.executors.timing_probability.random.uniform",
        lambda _start, _end: 25.0,
    )
    context = ExecutionContext()
    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        {
            "nodes": [
                {
                    "id": "choice",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "probability_trigger",
                        "config": {"probability": 50},
                    },
                },
                {
                    "id": "one",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "set_variable",
                        "config": {
                            "variableName": "selected",
                            "variableValue": "one",
                        },
                    },
                },
                {
                    "id": "two",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "set_variable",
                        "config": {
                            "variableName": "selected",
                            "variableValue": "two",
                        },
                    },
                },
            ],
            "edges": [
                {
                    "id": "path-one",
                    "source": "choice",
                    "sourceHandle": "path1",
                    "target": "one",
                },
                {
                    "id": "path-two",
                    "source": "choice",
                    "sourceHandle": "path2",
                    "target": "two",
                },
            ],
        },
        context,
    )

    assert result.success is True
    assert result.executed_node_ids == ("choice", "one")
    assert context.variables["selected"] == "one"
