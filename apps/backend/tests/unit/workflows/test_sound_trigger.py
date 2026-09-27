from __future__ import annotations

import pytest

from autoflow.application.workflows.executors import sound_trigger
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext


class _Meter:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def GetPeakValue(self) -> float:
        return self.values.pop(0)


@pytest.mark.asyncio
async def test_sound_trigger_waits_for_threshold_and_writes_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sound_trigger, "_audio_meter", lambda: _Meter([0.2, 0.67]))
    executor = build_production_executor_registry().get("sound_trigger")
    assert executor is not None
    context = ExecutionContext()
    result = await executor.execute(
        {
            "volumeThreshold": 50,
            "checkInterval": 0,
            "saveToVariable": "volume",
        },
        context,
    )

    assert result.success is True
    assert result.data == {"volume": 67}
    assert context.variables["volume"] == 67


@pytest.mark.asyncio
async def test_sound_trigger_timeout_precedes_another_meter_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meter = _Meter([0.1])
    times = iter((0.0, 2.0))
    monkeypatch.setattr(sound_trigger, "_audio_meter", lambda: meter)
    monkeypatch.setattr(sound_trigger, "_monotonic", lambda: next(times))
    executor = build_production_executor_registry().get("sound_trigger")
    assert executor is not None
    result = await executor.execute({"timeout": 1}, ExecutionContext())

    assert result.error == "声音触发器超时（1秒）"
    assert meter.values == [0.1]
