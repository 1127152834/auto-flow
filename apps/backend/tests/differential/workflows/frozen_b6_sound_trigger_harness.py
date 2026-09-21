# mypy: ignore-errors
from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace


class Meter:
    def __init__(self, values):
        self.values = list(values)

    def GetPeakValue(self):
        return self.values.pop(0)


meter = Meter([0.67])
interface = SimpleNamespace(QueryInterface=lambda _type: meter)
devices = SimpleNamespace(Activate=lambda *_args: interface)
audio_utilities = SimpleNamespace(GetSpeakers=lambda: devices)
meter_type = SimpleNamespace(_iid_="meter")
sys.modules["comtypes"] = SimpleNamespace(CLSCTX_ALL="all")
sys.modules["pycaw"] = SimpleNamespace()
sys.modules["pycaw.pycaw"] = SimpleNamespace(
    AudioUtilities=audio_utilities,
    IAudioMeterInformation=meter_type,
)

from app.executors.base import ExecutionContext  # noqa: E402
from app.executors.trigger import SoundTriggerExecutor  # noqa: E402


async def run(payload):
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await SoundTriggerExecutor().execute(payload.get("config", {}), context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


print(json.dumps(asyncio.run(run(json.loads(sys.stdin.read()))), ensure_ascii=False))
