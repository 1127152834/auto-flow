from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_waits_for_frontend_javascript_and_applies_result(
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            "js-run",
            "profile-1",
            None,
            {
                "runId": "js-run",
                "workflowId": "js-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": {
                    "nodes": [
                        {
                            "id": "script",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "js_script",
                                "config": {
                                    "code": "function main(vars){vars.count++;return 7}",
                                    "resultVariable": "answer",
                                },
                            },
                        },
                        {
                            "id": "after",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "print_log",
                                "config": {"logMessage": "{count}:{answer}"},
                            },
                        },
                    ],
                    "edges": [
                        {"id": "script-after", "source": "script", "target": "after"}
                    ],
                    "variables": [{"name": "count", "value": 1}],
                },
            },
        )
        for _ in range(300):
            if any(event.get("type") == "execution:js_script" for event in events):
                break
            await asyncio.sleep(0.01)
        request = next(
            event for event in events if event.get("type") == "execution:js_script"
        )
        assert request["code"] == "function main(vars){vars.count++;return 7}"
        assert request["variables"] == {"count": 1}
        assert not any(
            event.get("type") == "execution:node_complete" for event in events
        )

        await manager.send_command(
            "js-run",
            {
                "type": "js_script_result",
                "commandId": "result-1",
                "requestId": request["requestId"],
                "claimId": "studio",
                "success": True,
                "result": 7,
                "variables": {"count": 2, "notDeclared": 99},
            },
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert [event["nodeId"] for event in completed] == ["script", "after"]
        assert completed[0]["data"] == {"result": 7}
        assert completed[1]["message"] == "2:7"
        assert any(
            event.get("type") == "execution:command_applied"
            and event.get("commandId") == "result-1"
            for event in events
        )
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_frontend_javascript_failure_stops_following_nodes(tmp_path: Path) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    try:
        await manager.start(
            "js-fail-run",
            "profile-1",
            None,
            {
                "runId": "js-fail-run",
                "workflowId": "js-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "artifacts"),
                "document": {
                    "nodes": [
                        {
                            "id": "script",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "js_script",
                                "config": {"code": "throw Error('x')"},
                            },
                        },
                        {
                            "id": "after",
                            "type": "moduleNode",
                            "data": {
                                "moduleType": "print_log",
                                "config": {"logMessage": "must-not-run"},
                            },
                        },
                    ],
                    "edges": [
                        {"id": "script-after", "source": "script", "target": "after"}
                    ],
                    "variables": [],
                },
            },
        )
        for _ in range(300):
            requests = [
                event for event in events if event.get("type") == "execution:js_script"
            ]
            if requests:
                break
            await asyncio.sleep(0.01)
        request = requests[0]
        await manager.send_command(
            "js-fail-run",
            {
                "type": "js_script_result",
                "commandId": "failed-result",
                "requestId": request["requestId"],
                "claimId": "studio",
                "success": False,
                "error": "脚本错误",
            },
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert [event["nodeId"] for event in completed] == ["script"]
        assert completed[0]["success"] is False
        assert completed[0]["error"] == "JS脚本执行失败: 脚本错误"
        assert any(event.get("type") == "execution:failed" for event in events)
    finally:
        await manager.shutdown()
