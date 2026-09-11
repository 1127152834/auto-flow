from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, cast

KernelOperationState = Literal[
    "queued",
    "downloading",
    "verifying",
    "extracting",
    "cancelling",
    "cancelled",
    "completed",
    "failed",
]

ACTIVE_OPERATION_STATES: frozenset[KernelOperationState] = frozenset(
    {"queued", "downloading", "verifying", "extracting", "cancelling"}
)
TERMINAL_OPERATION_STATES: frozenset[KernelOperationState] = frozenset(
    {"cancelled", "completed", "failed"}
)

_TRANSITIONS: dict[KernelOperationState, frozenset[KernelOperationState]] = {
    "queued": frozenset({"downloading", "cancelling", "failed"}),
    "downloading": frozenset({"downloading", "verifying", "cancelling", "failed"}),
    "verifying": frozenset({"extracting", "cancelling", "failed"}),
    "extracting": frozenset({"completed", "cancelling", "failed"}),
    "cancelling": frozenset({"cancelled", "failed"}),
    "cancelled": frozenset(),
    "completed": frozenset(),
    "failed": frozenset(),
}


class InvalidKernelOperationTransition(RuntimeError):
    pass


@dataclass(frozen=True)
class KernelOperation:
    id: str
    edition: Literal["public", "licensed"]
    requested_version: str
    resolved_version: str | None
    release_channel: Literal["stable", "preview"]
    state: KernelOperationState
    progress: int | None
    message: str | None
    error: str | None

    @classmethod
    def new(
        cls,
        *,
        operation_id: str,
        edition: Literal["public", "licensed"],
        requested_version: str,
        release_channel: Literal["stable", "preview"],
        state: KernelOperationState = "queued",
    ) -> KernelOperation:
        return cls(
            id=operation_id,
            edition=edition,
            requested_version=requested_version,
            resolved_version=None,
            release_channel=release_channel,
            state=state,
            progress=None,
            message=None,
            error=None,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "edition": self.edition,
            "requestedVersion": self.requested_version,
            "resolvedVersion": self.resolved_version,
            "releaseChannel": self.release_channel,
            "state": self.state,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
        }


def transition_operation(
    operation: KernelOperation,
    state: str,
    *,
    progress: object = None,
    message: str | None = None,
    error: str | None = None,
    resolved_version: str | None = None,
) -> KernelOperation:
    if state not in _TRANSITIONS[operation.state]:
        raise InvalidKernelOperationTransition(f"{operation.state} -> {state}")
    typed_state = cast(KernelOperationState, state)
    normalized_progress = _progress(typed_state, progress)
    return replace(
        operation,
        state=typed_state,
        progress=normalized_progress,
        message=message,
        error=error,
        resolved_version=resolved_version or operation.resolved_version,
    )


def _progress(state: KernelOperationState, value: object) -> int | None:
    if state != "downloading" or value is None:
        return None
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError("download progress must be an integer from 0 to 100")
    return value
