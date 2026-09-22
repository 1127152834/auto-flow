from datetime import UTC, datetime, timedelta

import pytest

from autoflow.application.android.observations import DeviceObservationService


def test_stopped_snapshot_is_due_after_fifteen_seconds() -> None:
    service = DeviceObservationService({}, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    service.record("device-1", {"androidStatus": "stopped"}, at=datetime(2026, 1, 1, tzinfo=UTC))
    assert service.refresh_due(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=14)) == []
    assert service.refresh_due(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=15)) == ["device-1"]


def test_active_snapshot_becomes_stale_after_ten_seconds() -> None:
    service = DeviceObservationService({}, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    observation = service.record("device-1", {"androidStatus": "ready"}, at=datetime(2026, 1, 1, tzinfo=UTC))
    assert observation.stale is False
    assert service.get("device-1", at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=11)).stale is True


def test_active_snapshot_refreshes_after_three_seconds() -> None:
    service = DeviceObservationService({}, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    service.record("device-1", {"androidStatus": "ready"}, at=datetime(2026, 1, 1, tzinfo=UTC))
    assert service.refresh_due(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=2)) == []
    assert service.refresh_due(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=3)) == ["device-1"]


@pytest.mark.asyncio
async def test_failed_snapshot_marks_stale_and_backs_off() -> None:
    class Devices:
        def get(self, _device_id):
            return {"deviceId": "device-1"}

    class Runtime:
        async def inspect(self, _device):
            raise RuntimeError("runtime unavailable")

    service = DeviceObservationService(Devices(), Runtime(), now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    service.record("device-1", {"androidStatus": "ready"}, at=datetime(2026, 1, 1, tzinfo=UTC))
    first = await service.snapshot("device-1")
    second = await service.snapshot("device-1")
    assert first.stale and second.stale and second.error == "runtime unavailable"
    assert service.refresh_due(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=3)) == []
    assert service.refresh_due(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=6)) == ["device-1"]


@pytest.mark.asyncio
async def test_snapshot_projects_observation_into_device_repository() -> None:
    class Devices:
        def __init__(self):
            self.device = {"deviceId": "device-1", "androidStatus": "starting"}

        def get(self, _device_id):
            return self.device

        def save(self, device):
            self.device = device

    class Runtime:
        async def inspect(self, _device):
            return {"androidStatus": "ready", "lastError": None}

    devices = Devices()
    service = DeviceObservationService(devices, Runtime(), now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    await service.snapshot("device-1")
    assert devices.device["androidStatus"] == "ready"
    assert devices.device["stale"] is False
    assert devices.device["observedAt"] == "2026-01-01T00:00:00+00:00"
