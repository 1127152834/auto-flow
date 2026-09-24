# mypy: ignore-errors
from __future__ import annotations

import json
import sys

from app.services.gesture_recognition_service import GestureRecognitionService

payload = json.loads(sys.stdin.read())
service = GestureRecognitionService.__new__(GestureRecognitionService)
service.custom_gestures = payload["gestures"]
service.match_threshold = payload["threshold"]
print(
    json.dumps(
        {
            "similarity": float(
                service.calculate_gesture_similarity(
                    payload["current"], payload["reference"]
                )
            ),
            "match": service.match_gesture(payload["current"]),
        },
        ensure_ascii=False,
    )
)
