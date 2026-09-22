import pytest

from autoflow.domain.android.ports import AndroidError
from tests.fixtures.android_management import (
    DEVICE_ID,
    PROFILE_ID,
    MemoryDeviceRepository,
)


def test_fixture_ids_are_valid_and_distinct() -> None:
    from uuid import UUID

    assert UUID(DEVICE_ID) != UUID(PROFILE_ID)


def test_unknown_device_read_does_not_create_a_record() -> None:
    repository = MemoryDeviceRepository()

    with pytest.raises(AndroidError) as error:
        repository.get(DEVICE_ID)

    assert error.value.status == 404
    assert repository.list() == []


def test_device_view_does_not_invent_unverified_android_version() -> None:
    from autoflow.application.android.devices import device_view

    result = device_view({"deviceId": DEVICE_ID, "name": "设备", "imageId": "sha256:" + "a" * 64})

    assert result["androidVersion"] is None
    assert result["architecture"] is None


def test_device_view_does_not_invent_unverified_profile_name() -> None:
    from autoflow.application.android.devices import device_view

    result = device_view({"deviceId": DEVICE_ID, "name": "设备", "imageId": "sha256:" + "a" * 64})

    assert result["profileName"] is None


def test_runtime_new_device_keeps_unknown_profile_name_unknown(tmp_path) -> None:
    from autoflow.providers.android.mac_runtime import MacAndroidRuntime

    runtime = MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    device = runtime.new_device(
        {
            "deviceId": DEVICE_ID,
            "name": "设备",
            "imageId": "sha256:" + "a" * 64,
            "width": 720,
            "height": 1280,
            "dpi": 320,
            "cpu": 1,
            "memoryMb": 1536,
        }
    )

    assert device["profileName"] is None


def test_android_device_read_keeps_omitted_profile_name_unknown() -> None:
    from autoflow.adapters.http.android import AndroidDeviceRead

    result = AndroidDeviceRead.model_validate(
        {
            "deviceId": DEVICE_ID,
            "name": "设备",
            "runtimeId": "lima",
            "ownerRunId": None,
            "control": "idle",
            "generation": 0,
            "width": 720,
            "height": 1280,
            "imageId": "sha256:" + "a" * 64,
            "androidStatus": "unknown",
            "lastError": None,
        }
    )

    assert result.profile_name is None
