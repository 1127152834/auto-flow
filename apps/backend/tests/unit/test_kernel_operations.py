import pytest

from autoflow.application.kernels.operations import (
    InvalidKernelOperationTransition,
    KernelOperation,
    transition_operation,
)


def _operation(state: str = "queued") -> KernelOperation:
    return KernelOperation.new(
        operation_id="operation-1",
        edition="public",
        requested_version="146.0.7680.80",
        release_channel="stable",
        state=state,
    )


def test_operation_follows_install_state_machine() -> None:
    operation = _operation()
    for state in ("downloading", "verifying", "extracting", "completed"):
        operation = transition_operation(operation, state, progress=None)
    assert operation.state == "completed"
    assert operation.progress is None


@pytest.mark.parametrize("state", ["queued", "downloading", "verifying", "extracting"])
def test_active_operation_can_be_cancelled(state: str) -> None:
    operation = transition_operation(_operation(state), "cancelling")
    assert transition_operation(operation, "cancelled").state == "cancelled"


@pytest.mark.parametrize("state", ["completed", "cancelled", "failed"])
def test_terminal_operation_is_immutable(state: str) -> None:
    with pytest.raises(InvalidKernelOperationTransition):
        transition_operation(_operation(state), "failed")


def test_progress_is_only_kept_while_downloading() -> None:
    downloading = transition_operation(_operation(), "downloading", progress=62)
    assert downloading.progress == 62
    downloading = transition_operation(downloading, "downloading", progress=75)
    assert downloading.progress == 75
    verifying = transition_operation(downloading, "verifying", progress=99)
    assert verifying.progress is None


@pytest.mark.parametrize("progress", [-1, 101, 1.5, True])
def test_invalid_download_progress_is_rejected(progress: object) -> None:
    with pytest.raises(ValueError):
        transition_operation(_operation(), "downloading", progress=progress)
