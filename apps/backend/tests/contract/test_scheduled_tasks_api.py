from __future__ import annotations

from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings


def _client(tmp_path) -> TestClient:
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="scheduled-tasks",
            instance_token="renderer",
        )
    )
    return TestClient(app, headers={"x-autoflow-token": "renderer"})


def test_scheduled_task_crud_persists_across_service_restart(tmp_path) -> None:
    request = {
        "name": "每日网页任务",
        "workflow_id": "daily.json",
        "workflow_name": "每日流程",
        "enabled": True,
        "trigger": {
            "type": "time",
            "schedule_type": "daily",
            "daily_time": "08:30:00",
        },
    }
    with _client(tmp_path) as client:
        created = client.post("/api/scheduled-tasks", json=request)
        assert created.status_code == 201
        task = created.json()
        assert task["id"]
        assert task["revision"] == 1
        assert task["total_executions"] == 0
        assert task["timezone"] == "Asia/Shanghai"
        assert task["missed_trigger_policy"] == "skip"
        assert task["next_execution_time"]
        assert client.get("/api/scheduled-tasks/list").json() == [task]

        changed = client.put(
            f"/api/scheduled-tasks/{task['id']}",
            json={"name": "修改后", "expected_revision": 1},
        )
        assert changed.status_code == 200
        assert changed.json()["name"] == "修改后"
        assert changed.json()["revision"] == 2

        paused = client.post(f"/api/scheduled-tasks/{task['id']}/toggle", json={"enabled": False})
        assert paused.status_code == 200
        assert paused.json()["next_execution_time"] is None

        stale = client.put(
            f"/api/scheduled-tasks/{task['id']}",
            json={"name": "过期修改", "expected_revision": 1},
        )
        assert stale.status_code == 409

    with _client(tmp_path) as reopened:
        loaded = reopened.get(f"/api/scheduled-tasks/{task['id']}")
        assert loaded.status_code == 200
        assert loaded.json()["name"] == "修改后"
        assert reopened.delete(f"/api/scheduled-tasks/{task['id']}").status_code == 200
        assert reopened.get(f"/api/scheduled-tasks/{task['id']}").status_code == 404


def test_scheduled_task_rejects_invalid_trigger_without_persisting(tmp_path) -> None:
    with _client(tmp_path) as client:
        invalid = client.post(
            "/api/scheduled-tasks",
            json={
                "name": "坏任务",
                "workflow_id": "daily.json",
                "trigger": {
                    "type": "time",
                    "schedule_type": "interval",
                    "interval_seconds": 0,
                },
            },
        )
        assert invalid.status_code == 422
        assert client.get("/api/scheduled-tasks/list").json() == []


def test_hotkey_registrations_are_host_consumable_and_unique(tmp_path) -> None:
    request = {
        "name": "热键任务",
        "workflow_id": "missing.json",
        "profile_id": "profile-main",
        "trigger": {"type": "hotkey", "hotkey": "ctrl+shift+k"},
    }
    with _client(tmp_path) as client:
        created = client.post("/api/scheduled-tasks", json=request)
        assert created.status_code == 201
        task = created.json()
        assert client.get("/api/scheduled-tasks/hotkeys/registrations").json() == [
            {"task_id": task["id"], "hotkey": "ctrl+shift+k"}
        ]
        duplicate = client.post(
            "/api/scheduled-tasks",
            json={**request, "name": "冲突任务", "trigger": {"type": "hotkey", "hotkey": "CTRL+SHIFT+K"}},
        )
        assert duplicate.status_code == 409
        missing_workflow = client.post(
            f"/api/scheduled-tasks/hotkeys/{task['id']}/trigger",
            headers={"Idempotency-Key": "hotkey-command"},
        )
        assert missing_workflow.status_code == 404
        assert client.get("/api/scheduled-tasks/commands/hotkey-command").status_code == 200
