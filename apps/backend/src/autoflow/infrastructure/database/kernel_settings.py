import json
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.kernels.errors import KernelDefaultConflict
from autoflow.domain.kernels.models import DefaultKernel, KernelRef

from .models import KernelSettingsRow

_DEFAULT_KEY = "default"


class SqlAlchemyDefaultKernelRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        with self._session_factory.begin() as session:
            if session.get(KernelSettingsRow, _DEFAULT_KEY) is None:
                session.add(KernelSettingsRow(key=_DEFAULT_KEY, value="null", revision=0))

    def get(self) -> DefaultKernel:
        with self._session_factory() as session:
            row = session.get(KernelSettingsRow, _DEFAULT_KEY)
            assert row is not None
            return DefaultKernel(row.revision, _decode(row.value))

    def compare_and_set(
        self, expected_revision: int, kernel: KernelRef | None
    ) -> DefaultKernel:
        with self._session_factory.begin() as session:
            result = session.execute(
                update(KernelSettingsRow)
                .where(
                    KernelSettingsRow.key == _DEFAULT_KEY,
                    KernelSettingsRow.revision == expected_revision,
                )
                .values(value=_encode(kernel), revision=KernelSettingsRow.revision + 1)
            )
            if getattr(result, "rowcount", 0) != 1:
                raise KernelDefaultConflict()
        return DefaultKernel(expected_revision + 1, kernel)

    def clear_if_matches(self, kernel: KernelRef) -> DefaultKernel:
        with self._session_factory.begin() as session:
            row = session.get(KernelSettingsRow, _DEFAULT_KEY)
            assert row is not None
            current = _decode(row.value)
            if current == kernel:
                row.value = "null"
                row.revision += 1
                return DefaultKernel(row.revision, None)
            return DefaultKernel(row.revision, current)


def _encode(kernel: KernelRef | None) -> str:
    if kernel is None:
        return "null"
    return json.dumps(
        {"edition": kernel.edition, "version": kernel.version}, separators=(",", ":")
    )


def _decode(value: str) -> KernelRef | None:
    try:
        raw: Any = json.loads(value)
    except (TypeError, ValueError):
        raise KernelDefaultConflict() from None
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise KernelDefaultConflict()
    edition, version = raw.get("edition"), raw.get("version")
    if edition not in {"public", "licensed"} or not isinstance(version, str):
        raise KernelDefaultConflict()
    return KernelRef(edition, version)
