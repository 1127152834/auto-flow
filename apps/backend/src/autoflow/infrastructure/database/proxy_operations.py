from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from autoflow.domain.proxies.errors import (
    OperationInProgressError,
    ProxyNotFoundError,
    RevisionConflictError,
)
from autoflow.domain.proxies.remote import OperationStatus, RemoteOperation

from .proxy_models import ProxyConnectionRow, ProxyOperationRow, ProxyProjectionRow

KINDS = ("change_ip", "relocate", "save_rotation", "clear_rotation")
ACTIVE = ("queued", "running", "unknown")


class SqlAlchemyProxyOperations:
    def __init__(self, session_factory):
        self._sessions = session_factory

    def find_key(self, key: str) -> RemoteOperation | None:
        with self._sessions() as session:
            row = session.scalar(
                select(ProxyOperationRow).where(
                    ProxyOperationRow.idempotency_key == key
                )
            )
            return _value(row) if row else None

    def get(self, operation_id: str) -> RemoteOperation:
        with self._sessions() as session:
            row = session.get(ProxyOperationRow, operation_id)
            if row is None or row.kind not in KINDS:
                raise ProxyNotFoundError("找不到代理操作记录")
            return _value(row)

    def active(self, target_id: str) -> RemoteOperation | None:
        with self._sessions() as session:
            row = session.scalar(
                select(ProxyOperationRow).where(
                    ProxyOperationRow.target_id == target_id,
                    ProxyOperationRow.kind.in_(KINDS),
                    ProxyOperationRow.status.in_(ACTIVE),
                )
            )
            return _value(row) if row else None

    def latest(self, target_id: str) -> RemoteOperation | None:
        with self._sessions() as session:
            row = session.scalar(
                select(ProxyOperationRow)
                .where(
                    ProxyOperationRow.target_id == target_id,
                    ProxyOperationRow.kind.in_(KINDS),
                )
                .order_by(ProxyOperationRow.created_at.desc())
                .limit(1)
            )
            return _value(row) if row else None

    def reserve(
        self, operation: RemoteOperation, expected_revision: int
    ) -> RemoteOperation:
        try:
            with self._sessions() as session:
                session.execute(text("BEGIN IMMEDIATE"))
                existing = session.scalar(
                    select(ProxyOperationRow).where(
                        ProxyOperationRow.idempotency_key == operation.idempotency_key
                    )
                )
                if existing:
                    return _value(existing)
                proxy = session.get(ProxyProjectionRow, operation.target_id)
                connection = session.get(ProxyConnectionRow, operation.connection_id)
                if (
                    proxy is None
                    or proxy.revision != expected_revision
                    or connection is None
                    or connection.secret_ref != operation.secret_ref
                ):
                    raise RevisionConflictError("代理或连接已变化，请刷新后重试")
                session.add(ProxyOperationRow(**asdict(operation)))
                session.commit()
            return operation
        except IntegrityError:
            raise OperationInProgressError(
                "此代理已有进行中或结果待确认的操作，请先查看并核实"
            ) from None

    def update(
        self,
        operation_id: str,
        status: OperationStatus,
        *,
        before: dict | None = None,
        error: dict | None = None,
        resource_revision: int | None = None,
    ) -> None:
        values: dict = {
            "status": status,
            "error": error,
            "resource_revision": resource_revision,
            "updated_at": datetime.now(UTC),
        }
        if before is not None:
            values["before"] = before
        with self._sessions.begin() as session:
            session.execute(
                update(ProxyOperationRow)
                .where(
                    ProxyOperationRow.id == operation_id,
                    ProxyOperationRow.status.in_(ACTIVE),
                )
                .values(**values)
            )

    def recover(self) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(ProxyOperationRow)
                .where(
                    ProxyOperationRow.kind.in_(KINDS),
                    ProxyOperationRow.status == "queued",
                )
                .values(
                    status="failed",
                    updated_at=datetime.now(UTC),
                    error={
                        "code": "PROXY_COMMAND_INTERRUPTED",
                        "message": "应用在发送操作前退出，请重新发起",
                    },
                )
            )
            session.execute(
                update(ProxyOperationRow)
                .where(
                    ProxyOperationRow.kind.in_(KINDS),
                    ProxyOperationRow.status == "running",
                )
                .values(
                    status="unknown",
                    updated_at=datetime.now(UTC),
                    error={
                        "code": "PROXYPANEL_OUTCOME_UNKNOWN",
                        "message": "应用退出时操作结果尚未确认，请重新核实；不会自动重发",
                    },
                )
            )


def _value(row) -> RemoteOperation:
    return RemoteOperation(
        **{name: getattr(row, name) for name in RemoteOperation.__dataclass_fields__}
    )
