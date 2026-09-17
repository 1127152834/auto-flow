from copy import deepcopy
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.android.ports import AndroidError

from .android_models import AndroidDeviceRow


class SqlAlchemyDeviceRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def list(self) -> list[dict[str, Any]]:
        with self.sessions() as session:
            return [deepcopy(row.payload) for row in session.scalars(select(AndroidDeviceRow))]

    def get(self, device_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(AndroidDeviceRow, device_id)
            if row is None:
                raise AndroidError("ANDROID_NOT_FOUND", "安卓设备未登记", 404)
            return deepcopy(row.payload)

    def save(self, device: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            session.merge(AndroidDeviceRow(id=device["deviceId"], owner_run_id=device.get("ownerRunId"), payload=deepcopy(device)))

    def claim(self, device_id: str, run_id: str) -> dict[str, Any]:
        with self.sessions.begin() as session:
            row = session.get(AndroidDeviceRow, device_id)
            if row is None:
                raise AndroidError("ANDROID_NOT_FOUND", "安卓设备未登记", 404)
            device = deepcopy(row.payload)
            if device.get("deleted"):
                raise AndroidError("ANDROID_NOT_FOUND", "设备已删除", 404)
            if device.get("control") != "idle":
                raise AndroidError("ANDROID_BUSY", "设备已占用或需要恢复")
            device.update(ownerRunId=run_id, control="workflow", generation=device.get("generation", 0) + 1)
            result = session.execute(update(AndroidDeviceRow).where(
                AndroidDeviceRow.id == device_id, AndroidDeviceRow.owner_run_id.is_(None),
            ).values(owner_run_id=run_id, payload=device))
            if cast(CursorResult, result).rowcount != 1:
                raise AndroidError("ANDROID_BUSY", "设备已被其他运行占用")
            return device
