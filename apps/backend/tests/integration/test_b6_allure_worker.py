from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


@pytest.mark.asyncio
async def test_real_worker_builds_and_registers_allure_report(tmp_path: Path) -> None:
    events: list[dict[str, object]] = []
    manager = WorkflowWorkerManager(
        tmp_path,
        termination_timeout=0.5,
        on_event=lambda event: events.append(event),
    )
    workspace = tmp_path / "workspace"
    attachment = tmp_path / "attachment.txt"
    attachment.write_text("worker 附件", encoding="utf-8")
    module_types = [
        "allure_init",
        "allure_start_test",
        "allure_add_step",
        "allure_add_attachment",
        "allure_stop_test",
        "allure_generate_report",
    ]
    configs = [
        {"testSuite": "Worker 回归"},
        {"name": "真实执行"},
        {"name": "生成报告"},
        {"filePath": str(attachment)},
        {"status": "passed"},
        {"reportDir": "allure", "autoOpen": True},
    ]
    document = {
        "nodes": [
            {
                "id": f"node-{index}",
                "type": "moduleNode",
                "data": {"moduleType": module_type, "config": configs[index]},
            }
            for index, module_type in enumerate(module_types)
        ],
        "edges": [
            {
                "id": f"edge-{index}",
                "source": f"node-{index}",
                "target": f"node-{index + 1}",
            }
            for index in range(len(module_types) - 1)
        ],
        "variables": [],
    }
    try:
        await manager.start(
            "allure-run",
            "profile-1",
            None,
            {
                "runId": "allure-run",
                "workflowId": "allure-flow",
                "profileId": "profile-1",
                "requiresBrowser": False,
                "artifactRoot": str(workspace),
                "document": document,
            },
        )
        for _ in range(500):
            requests = [
                event
                for event in events
                if event.get("type") == "execution:desktop_action"
            ]
            if requests:
                break
            await asyncio.sleep(0.01)
        request = requests[0]
        assert request["action"] == "open_path"
        assert str(request["payload"]["path"]).endswith(".html")
        await manager.send_command(
            "allure-run",
            {
                "type": "desktop_action_result",
                "commandId": "open-report",
                "requestId": request["requestId"],
                "claimId": "studio",
                "success": True,
            },
        )
        for _ in range(500):
            if not manager.busy():
                break
            await asyncio.sleep(0.01)

        report = next(
            (workspace / "runs" / "allure-run" / "outputs" / "allure").glob(
                "report_*.html"
            )
        )
        content = report.read_text(encoding="utf-8")
        completed = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        registered = [
            event for event in events if event.get("type") == "artifact:registered"
        ]

        assert manager.busy() is False
        assert [event["nodeId"] for event in completed] == [
            f"node-{index}" for index in range(6)
        ]
        assert all(event["success"] is True for event in completed)
        assert len(registered) == 1
        assert registered[0]["nodeId"] == "node-5"
        assert all(
            value in content
            for value in ("Worker 回归", "真实执行", "生成报告", "worker 附件")
        )
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()
