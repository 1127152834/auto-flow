from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager
from autoflow.infrastructure.sharing import NetworkShareHost


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _payload(run_id: str, module_type: str, config: dict[str, object], root: Path):
    return {
        "runId": run_id,
        "workflowId": "share-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(root / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "share",
                    "type": "moduleNode",
                    "data": {"moduleType": module_type, "config": config},
                }
            ],
            "edges": [],
            "variables": [],
        },
    }


async def _wait(manager: WorkflowWorkerManager) -> None:
    for _ in range(500):
        if not manager.busy():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("workflow worker did not finish")


@pytest.mark.asyncio
async def test_file_share_outlives_start_worker_and_stop_node_cleans_it(
    tmp_path: Path,
) -> None:
    file = tmp_path / "shared.txt"
    file.write_text("persistent", encoding="utf-8")
    port = _port()
    host = NetworkShareHost()
    events: list[dict[str, object]] = []
    manager: WorkflowWorkerManager

    async def on_event(event: dict[str, object]) -> None:
        if event.get("type") == "execution:desktop_action" and host.supports(
            event.get("action")
        ):
            result = await host.perform(
                str(event["action"]),
                event["payload"] if isinstance(event.get("payload"), dict) else {},
            )
            await manager.send_command(
                str(event["runId"]),
                {
                    "type": "desktop_action_result",
                    "commandId": str(uuid4()),
                    "requestId": event["requestId"],
                    "success": result.success,
                    "value": result.value,
                    "error": result.error,
                },
            )
            return
        events.append(event)

    manager = WorkflowWorkerManager(
        tmp_path / "workers",
        termination_timeout=0.5,
        on_event=on_event,
    )
    try:
        await manager.start(
            "share-start",
            "profile-1",
            None,
            _payload(
                "share-start",
                "share_file",
                {"filePath": str(file), "port": port},
                tmp_path,
            ),
        )
        await _wait(manager)
        assert host.busy()
        assert any(event.get("type") == "execution:completed" for event in events)
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(f"http://127.0.0.1:{port}/download")
        assert response.content == b"persistent"

        events.clear()
        await manager.start(
            "share-stop",
            "profile-1",
            None,
            _payload("share-stop", "stop_share", {"port": port}, tmp_path),
        )
        await _wait(manager)
        assert host.busy() is False
        assert any(event.get("type") == "execution:completed" for event in events)
    finally:
        await manager.shutdown()
        await host.shutdown()
