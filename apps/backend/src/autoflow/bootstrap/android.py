from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from autoflow.providers.android.mac_runtime import MacAndroidRuntime, png_size


def android_service(sessions: sessionmaker[Session], workspace: Path) -> AndroidDeviceService:
    return AndroidDeviceService(SqlAlchemyDeviceRepository(sessions), MacAndroidRuntime(android_runtime_root(), workspace))


def save_android_image(runs_root: Path, run_id: str, node_id: str, data: bytes) -> dict[str, Any]:
    width, height = png_size(data)
    artifact = WorkflowArtifacts(runs_root, run_id).save_png(node_id, data, "")
    artifact["preview"] = f"Android · {width} × {height}"
    return {"artifact": artifact, "value": {"artifactId": artifact["id"], "width": width, "height": height}}
