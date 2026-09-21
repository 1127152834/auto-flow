ENVIRONMENT_RESERVE_BYTES = 512 * 1024**2


def can_admit(
    total_memory: int | None,
    running_limits: int | None,
    reserved_memory: int | None,
    requested_memory: int | None,
) -> bool:
    """Return whether a request fits after existing usage and the safety reserve."""
    values = (total_memory, running_limits, reserved_memory, requested_memory)
    if any(value is None or not isinstance(value, int) or value < 0 for value in values):
        return False
    return running_limits + reserved_memory + requested_memory + ENVIRONMENT_RESERVE_BYTES <= total_memory
