from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from autoflow.application.workflows.executors.text_to_speech import (
    TextToSpeechExecutor,
)
from autoflow.domain.workflows.execution import ExecutionContext, SpeechResult

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b6_text_to_speech_harness.py")


class SpeechGateway:
    async def speak(self, *_args, **_kwargs) -> SpeechResult:  # type: ignore[no-untyped-def]
        return SpeechResult(True)


def _source(payload: dict) -> dict:  # type: ignore[type-arg]
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.asyncio
async def test_renderer_speech_success_matches_frozen_source() -> None:
    payload = {
        "config": {
            "text": "通知",
            "lang": "zh-CN",
            "rate": 0.8,
            "pitch": 1.2,
            "volume": 0,
        },
        "variables": {},
    }
    context = ExecutionContext(speech=SpeechGateway())
    target = await TextToSpeechExecutor().execute(payload["config"], context)

    assert {
        "result": {
            "success": target.success,
            "message": target.message,
            "data": target.data,
            "error": target.error,
            "branch": target.branch,
            "skipped": target.skipped,
        },
        "variables": context.variables,
    } == _source(payload)
