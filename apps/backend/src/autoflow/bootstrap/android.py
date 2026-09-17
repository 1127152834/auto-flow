from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.providers.android.mac_runtime import MacAndroidRuntime


class CurrentAndroidRunBoundary:
    """Expose current-run absence explicitly without importing the retired M5 runtime."""

    def device_context(self, _device_id: str) -> None:
        return None

    def request_takeover(self, _device_id: str) -> None:
        raise AndroidError(
            "ANDROID_TAKEOVER_UNAVAILABLE",
            "当前运行不属于安卓执行器，无法申请工作流接管",
            409,
        )

    def list(self, *_args: Any) -> dict[str, Any]:
        return {"items": [], "total": 0, "nextCursor": None}

    def get(self, _run_id: str) -> dict[str, Any]:
        raise AndroidError("ANDROID_RUN_NOT_FOUND", "安卓运行记录不存在", 404)

    async def start(self, *_args: Any, **_kwargs: Any) -> None:
        raise AndroidError(
            "ANDROID_WORKFLOW_RUNTIME_UNAVAILABLE",
            "当前 Studio 尚未提供安卓工作流执行契约",
            409,
        )


def android_service(sessions: sessionmaker[Session], workspace: Path) -> AndroidDeviceService:
    return AndroidDeviceService(SqlAlchemyDeviceRepository(sessions), MacAndroidRuntime(android_runtime_root(), workspace))
