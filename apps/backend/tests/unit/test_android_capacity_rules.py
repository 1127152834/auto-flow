from autoflow.domain.android.capacity_rules import can_admit


def test_unknown_memory_is_not_zero() -> None:
    assert can_admit(8 * 1024**3, None, 0, 1536 * 1024**2) is False


def test_reservations_count_towards_capacity() -> None:
    assert can_admit(4 * 1024**3, 2 * 1024**3, 1024**3, 1024**3) is False


def test_capacity_keeps_environment_reserve() -> None:
    assert can_admit(4 * 1024**3, 1024**3, 0, 1536 * 1024**2) is True
