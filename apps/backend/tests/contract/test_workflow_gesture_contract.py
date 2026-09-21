from __future__ import annotations

from typing import Any

from autoflow.adapters.http.workflow_gestures import workflow_gesture_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class GestureService:
    def __init__(self) -> None:
        self.names = ["点赞"]
        self.recorded: tuple[str, int, float] | None = None

    def list_custom_gestures(self) -> list[dict[str, str]]:
        return [{"name": name, "type": "custom"} for name in self.names]

    def get_status(self) -> dict[str, Any]:
        return {
            "is_running": False,
            "camera_index": 0,
            "debug_window": False,
            "gesture_count": len(self.names),
        }

    def record_gesture(
        self, gesture_name: str, camera_index: int = 0, timeout: float = 30
    ) -> bool:
        self.recorded = (gesture_name, camera_index, timeout)
        self.names.append(gesture_name)
        return True

    def delete_gesture(self, gesture_name: str) -> bool:
        if gesture_name not in self.names:
            return False
        self.names.remove(gesture_name)
        return True


def test_frontend_gesture_tool_contract() -> None:
    service = GestureService()
    app = FastAPI()
    app.include_router(workflow_gesture_router(service))
    client = TestClient(app)

    listed = client.get("/api/triggers/gesture/custom")
    status = client.get("/api/triggers/gesture/status")
    recorded = client.post(
        "/api/triggers/gesture/record",
        json={"gesture_name": "OK 手势", "timeout": 30},
    )
    deleted = client.delete("/api/triggers/gesture/custom/OK%20%E6%89%8B%E5%8A%BF")
    missing = client.delete("/api/triggers/gesture/custom/not-found")

    assert listed.json() == {
        "success": True,
        "gestures": [{"name": "点赞", "type": "custom"}],
    }
    assert status.json()["status"]["gesture_count"] == 1
    assert recorded.json()["gesture_name"] == "OK 手势"
    assert service.recorded == ("OK 手势", 0, 30)
    assert deleted.status_code == 200
    assert missing.status_code == 404
