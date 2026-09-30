ENVIRONMENT_RESERVE_BYTES = 512 * 1024**2


def can_admit(
    total_memory: int | None,
    running_limits: int | None,
    reserved_memory: int | None,
    requested_memory: int | None,
) -> bool:
    """Return whether a request fits after existing usage and the safety reserve."""
    if (
        not isinstance(total_memory, int)
        or not isinstance(running_limits, int)
        or not isinstance(reserved_memory, int)
        or not isinstance(requested_memory, int)
        or min(total_memory, running_limits, reserved_memory, requested_memory) < 0
    ):
        return False
    return running_limits + reserved_memory + requested_memory + ENVIRONMENT_RESERVE_BYTES <= total_memory
