"""Read-only Mac/Lima disk diagnostics through the real HTTP response contract."""
import json
import tempfile
from pathlib import Path

from autoflow.adapters.http.android_management import android_management_router
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.providers.android.mac_runtime import MacAndroidRuntime
from fastapi import FastAPI
from fastapi.testclient import TestClient


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="autoflow-disk-observation-") as workspace:
        runtime = MacAndroidRuntime(Path.home() / ".autoflow/android-runtime", Path(workspace))
        app = FastAPI()
        app.include_router(android_management_router(EnvironmentCheckService(runtime)))
        with TestClient(app) as client:
            response = client.get("/api/v1/android/management/environment")
        assert response.status_code == 200, response.text
        body = response.json()
        result = {key: body[key] for key in (
            "checkedAt", "runtimeId", "available", "hostWorkspaceFreeBytes", "vmDockerFreeBytes",
        )}
        result["diskCheck"] = body["checks"]["disk"]
        result["transport"] = "in-process HTTP; real Mac/Lima probes, no device mutations"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        assert body["hostWorkspaceFreeBytes"] > 0
        assert body["vmDockerFreeBytes"] > 0
        assert body["checks"]["disk"]["status"] == "pass"


if __name__ == "__main__":
    main()
