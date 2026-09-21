import pytest

from autoflow.application.android.capacity import admit
from autoflow.domain.android.ports import AndroidError


def test_capacity_reserves_host_memory_and_unknown_state_blocks():
    assert admit({"cpu": 1, "memoryMb": 1024}, {"cpu": 4, "memoryMb": 8192, "usedMb": 1024}) is True
    with pytest.raises(AndroidError):
        admit({"cpu": 1, "memoryMb": 1024}, {"cpu": 4, "memoryMb": None, "usedMb": None})
