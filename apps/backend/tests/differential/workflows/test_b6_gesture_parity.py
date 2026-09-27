from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.infrastructure.gesture import GestureRecognitionService

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_gesture_harness.py")


def _landmarks(offset: float = 0) -> list[list[float]]:
    return [[offset + index / 100, index / 200, -index / 300] for index in range(21)]


def _source(payload: dict[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "reference" / "WebRPA" / "backend")
    completed = subprocess.run(
        [sys.executable, str(HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize("offset,threshold", [(0.0, 0.6), (0.01, 0.95)])
def test_gesture_similarity_and_matching_match_frozen_source(
    offset: float, threshold: float
) -> None:
    current = _landmarks(offset)
    reference = _landmarks()
    gestures = {"点赞": reference, "偏移": _landmarks(0.1)}
    payload = {
        "current": current,
        "reference": reference,
        "gestures": gestures,
        "threshold": threshold,
    }
    source = _source(payload)
    migrated_similarity = GestureRecognitionService.calculate_similarity(
        current, reference
    )
    migrated_match = GestureRecognitionService.match_gesture(
        current, gestures, threshold
    )

    assert migrated_similarity == pytest.approx(source["similarity"])
    assert migrated_match == source["match"]
