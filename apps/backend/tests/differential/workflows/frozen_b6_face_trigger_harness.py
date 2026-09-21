# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace


class Capture:
    def __init__(self, index):
        self.index = index
        self.frames = ["frame"]

    def isOpened(self):
        return True

    def read(self):
        return (True, self.frames.pop(0)) if self.frames else (False, None)

    def release(self):
        return None


face_recognition = SimpleNamespace(
    load_image_file=lambda _path: "target-image",
    face_locations=lambda _frame: [(1, 2, 3, 4)],
    face_encodings=lambda image, locations=None: (
        ["target"] if image == "target-image" else ["detected"]
    ),
    face_distance=lambda _targets, _detected: [0.25],
)
cv2 = SimpleNamespace(
    COLOR_BGR2RGB=1,
    VideoCapture=Capture,
    cvtColor=lambda frame, _conversion: frame,
)
sys.modules["face_recognition"] = face_recognition
sys.modules["cv2"] = cv2

from app.executors.base import ExecutionContext  # noqa: E402
from app.executors.trigger import FaceTriggerExecutor  # noqa: E402


async def run(payload):
    context = ExecutionContext()
    result = await FaceTriggerExecutor().execute(payload.get("config", {}), context)
    variables = dict(context.variables)
    for value in variables.values():
        if isinstance(value, dict):
            value.pop("timestamp", None)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
