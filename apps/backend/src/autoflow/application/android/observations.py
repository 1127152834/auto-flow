import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Observation:
    device_id: str
    runtime_state: str
    observed_at: datetime
    stale: bool = False
    error: str | None = None


class DeviceObservationService:
    def __init__(self, devices: Any, runtime: Any | None = None, now: Callable[[], datetime] | None = None) -> None:
        self.devices = devices
        self.runtime = runtime
        self.now = now or (lambda: datetime.now(UTC))
        self._observations: dict[str, Observation] = {}
        self._failures: dict[str, int] = {}
        self._task: asyncio.Task[None] | None = None
        self._closing = False

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._closing = False
            self._task = asyncio.create_task(self._loop(), name="android-observations")

    async def shutdown(self) -> None:
        self._closing = True
        if self._task is not None and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _loop(self) -> None:
        while not self._closing:
            current = self.now()
            known = set(self._observations)
            due = set(self.refresh_due(current))
            for device in self.devices.list():
                device_id = str(device.get("deviceId"))
                if device.get("deleted") or (device_id in known and device_id not in due):
                    continue
                await self.snapshot(device_id)
            await asyncio.sleep(3)

    def record(self, device_id: str, observed: dict[str, Any], at: datetime | None = None) -> Observation:
        observation = Observation(
            device_id=device_id,
            runtime_state=str(observed.get("androidStatus", "unknown")),
            observed_at=at or self.now(),
            stale=False,
            error=observed.get("lastError"),
        )
        self._observations[device_id] = observation
        self._failures.pop(device_id, None)
        self._project(observation)
        return observation

    def _project(self, observation: Observation) -> None:
        save = getattr(self.devices, "save", None)
        if save is None:
            return
        try:
            device = self.devices.get(observation.device_id)
            device.update(
                androidStatus=observation.runtime_state,
                observedAt=observation.observed_at.isoformat(),
                stale=observation.stale,
                lastError=observation.error,
            )
            save(device)
        except Exception:  # noqa: BLE001 - an in-memory observation still serves reads when projection is unavailable.
            return

    def get(self, device_id: str, at: datetime | None = None) -> Observation | None:
        observation = self._observations.get(device_id)
        if observation is None:
            return None
        current = at or self.now()
        age = max(0.0, (current - observation.observed_at).total_seconds())
        threshold = 10 if observation.runtime_state in {"ready", "starting"} else 45
        return Observation(**{**observation.__dict__, "stale": observation.stale or age >= threshold})

    def refresh_due(self, at: datetime | None = None) -> list[str]:
        current = at or self.now()
        due = []
        for device_id, observation in self._observations.items():
            failures = self._failures.get(device_id, 0)
            threshold = min(3 * (2 ** (failures - 1)), 30) if failures else (3 if observation.runtime_state in {"ready", "starting"} else 15)
            if (current - observation.observed_at).total_seconds() >= threshold:
                due.append(device_id)
        return sorted(due)

    async def snapshot(self, device_id: str) -> Observation:
        if self.runtime is None:
            raise RuntimeError("Android observation runtime is not configured")
        device = self.devices.get(device_id)
        try:
            observed = self.runtime.inspect(device)
            if inspect.isawaitable(observed):
                observed = await observed
        except Exception as error:  # noqa: BLE001 - retain the last state and expose a safe error.
            previous = self._observations.get(device_id)
            self._failures[device_id] = self._failures.get(device_id, 0) + 1
            observation = Observation(device_id, previous.runtime_state if previous else "unknown", self.now(), True, str(error)[:240])
            self._observations[device_id] = observation
            self._project(observation)
            return observation
        return self.record(device_id, observed)
