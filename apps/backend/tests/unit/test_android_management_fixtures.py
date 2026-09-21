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
