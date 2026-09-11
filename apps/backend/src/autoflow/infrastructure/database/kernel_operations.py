from __future__ import annotations

import builtins
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import select

from autoflow.application.kernels.operations import (
    ACTIVE_OPERATION_STATES,
    KernelOperation,
    KernelOperationState,
)

from .models import KernelOperationRow


class SqlAlchemyKernelOperationRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def save(self, operation: KernelOperation) -> None:
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            row = session.get(KernelOperationRow, operation.id)
            if row is None:
                row = KernelOperationRow(
                    id=operation.id,
                    kind="kernel_install",
                    status=operation.state,
                    result=_payload(operation),
                    error=_error(operation),
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.status = operation.state
                row.result = _payload(operation)
                row.error = _error(operation)
                row.updated_at = now

    def get(self, operation_id: str) -> KernelOperation | None:
        with self._session_factory() as session:
            row = session.get(KernelOperationRow, operation_id)
            return _operation(row) if row is not None else None

    def list(self) -> builtins.list[KernelOperation]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(KernelOperationRow)
                .where(KernelOperationRow.kind == "kernel_install")
                .order_by(KernelOperationRow.created_at, KernelOperationRow.id)
            )
            return [_operation(row) for row in rows]

    def list_active(self) -> builtins.list[KernelOperation]:
        return [item for item in self.list() if item.state in ACTIVE_OPERATION_STATES]


def _payload(operation: KernelOperation) -> dict[str, object]:
    return {
        "edition": operation.edition,
        "requestedVersion": operation.requested_version,
        "resolvedVersion": operation.resolved_version,
        "releaseChannel": operation.release_channel,
        "progress": operation.progress,
        "message": operation.message,
    }


def _error(operation: KernelOperation) -> dict[str, str] | None:
    return {"message": operation.error} if operation.error is not None else None


def _operation(row: KernelOperationRow) -> KernelOperation:
    payload = row.result or {}
    error = row.error or {}
    return KernelOperation(
        id=row.id,
        edition=cast(Literal["public", "licensed"], payload["edition"]),
        requested_version=str(payload["requestedVersion"]),
        resolved_version=_optional_string(payload.get("resolvedVersion")),
        release_channel=cast(Literal["stable", "preview"], payload["releaseChannel"]),
        state=cast(KernelOperationState, row.status),
        progress=_optional_int(payload.get("progress")),
        message=_optional_string(payload.get("message")),
        error=_optional_string(error.get("message")),
    )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if type(value) is int else None
