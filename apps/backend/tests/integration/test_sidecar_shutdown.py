from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from autoflow.infrastructure.database.kernel_operations import (
    SqlAlchemyKernelOperationRepository,
)
from autoflow.infrastructure.database.session import create_session_factory


@pytest.mark.asyncio
async def test_workflow_shutdown_error_still_closes_other_modules(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from autoflow.bootstrap.app import create_app
    from autoflow.bootstrap.config import Settings

    app = create_app(Settings(data_dir=str(tmp_path / 'shutdown-data'), instance_id='shutdown-fixture'))
    failed = AsyncMock(side_effect=RuntimeError('synthetic workflow cleanup failure'))
    monkeypatch.setattr(app.state.workflow_dispatcher, 'shutdown', failed)
    browser = AsyncMock(wraps=app.state.test_browser_worker_manager.shutdown)
    kernel = AsyncMock(wraps=app.state.kernel_worker_manager.shutdown)
    exports = Mock(wraps=app.state.excel_exports.shutdown)
    batches = Mock(wraps=app.state.status_batch_coordinator.shutdown)
    monkeypatch.setattr(app.state.test_browser_worker_manager, 'shutdown', browser)
    monkeypatch.setattr(app.state.kernel_worker_manager, 'shutdown', kernel)
    monkeypatch.setattr(app.state.excel_exports, 'shutdown', exports)
    monkeypatch.setattr(app.state.status_batch_coordinator, 'shutdown', batches)
    with pytest.raises(RuntimeError, match='synthetic workflow cleanup failure'):
        await app.router.on_shutdown[-1]()
    browser.assert_awaited_once()
    kernel.assert_awaited_once()
    exports.assert_called_once()
    batches.assert_called_once()


@pytest.mark.parametrize("shutdown", ["host", "signal"])
@pytest.mark.parametrize("active_worker", [False, True])
def test_open_sse_does_not_block_shutdown_or_worker_cleanup(
    tmp_path: Path, shutdown: str, active_worker: bool,
) -> None:
    if shutdown == "signal" and sys.platform == "win32":
        pytest.skip("Windows terminate is not a cooperative signal; host HTTP is tested")
    # Only the external wrapper is replaced. The real entrypoint, HTTP/SSE,
    # worker subprocess, manager, application cleanup and database all run.
    wrapper = tmp_path / "wrapper" / "cloakbrowser"
    wrapper.mkdir(parents=True)
    (wrapper / "__init__.py").write_text('''
import os, signal, time
from pathlib import Path

def ensure_binary(**kwargs):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    cache = Path(os.environ["CLOAKBROWSER_CACHE_DIR"])
    (cache / "partial").write_bytes(b"partial download")
    (cache / "worker.pid").write_text(str(os.getpid()))
    time.sleep(60)
''')
    env = {
        **os.environ,
        "AUTOFLOW_INSTANCE_TOKEN": "shutdown-test-token",
        "AUTOFLOW_HOST_TOKEN": "shutdown-host-token",
        "PYTHONPATH": os.pathsep.join((str(Path(__file__).parents[2] / "src"), str(wrapper.parent))),
    }
    data = tmp_path / "data"
    with (tmp_path / "stderr.log").open("w+") as stderr:
        process = subprocess.Popen(
            [sys.executable, "-m", "autoflow", "--instance-id", "shutdown-test",
             "--data-dir", str(data), "--port", "0"],
            env=env, stdout=subprocess.PIPE, stderr=stderr, text=True,
        )
        try:
            assert process.stdout is not None
            ready = json.loads(process.stdout.readline().removeprefix("AUTOFLOW_READY "))
            with httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}", trust_env=False, timeout=5) as client:
                headers = {"x-autoflow-token": "shutdown-test-token"}
                for bad_headers in ({}, headers, {
                    "x-autoflow-host-token": "shutdown-host-token", "origin": "null",
                }):
                    assert client.post("/internal/lifecycle/shutdown", headers=bad_headers).status_code == 401
                # Schema generation happens before the timed shutdown/SSE phase.
                # Give preparation its own bound without changing shutdown deadlines.
                schema = client.get("/openapi.json", timeout=30)
                assert schema.status_code == 200, schema.text
                assert "/internal/lifecycle/shutdown" not in schema.json()["paths"]
                operation = None
                if active_worker:
                    response = client.post("/api/v1/kernels/download", headers=headers, json={
                        "edition": "public", "version": "146.0.7680.80", "releaseChannel": "stable",
                    })
                    assert response.status_code == 202
                    operation = response.json()
                    staging = data / "data" / "kernels" / ".staging" / operation["id"]
                    # Wait for the fixture to start before measuring shutdown; cold
                    # interpreter startup under CI load is not shutdown latency.
                    deadline = time.monotonic() + 20
                    while not (staging / "worker.pid").exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    assert (staging / "worker.pid").is_file(), (tmp_path / "stderr.log").read_text(errors="replace")
                    worker_pid = int((staging / "worker.pid").read_text())
                with client.stream("GET", "/api/v1/kernels/events", headers=headers) as stream:
                    assert stream.status_code == 200
                    lines = stream.iter_lines()
                    assert next(lines) == "event: snapshot"
                    snapshot = json.loads(next(lines).removeprefix("data: "))
                    if operation:
                        assert snapshot["operations"][0]["state"] == "downloading"
                    started = time.monotonic()
                    if shutdown == "signal":
                        process.send_signal(signal.SIGTERM)
                    else:
                        response = client.post("/internal/lifecycle/shutdown", headers={
                            "x-autoflow-host-token": "shutdown-host-token",
                        })
                        assert response.json() == {"stopping": True}
                    # Keep the client stream open until the actual process exits.
                    code = process.wait(timeout=8 if active_worker else 3)
                    assert code == (0 if shutdown == "host" else -signal.SIGTERM)
                    assert time.monotonic() - started < (8 if active_worker else 3)
                if operation:
                    # Never signal PID 0 on Windows: OpenProcess checks liveness there.
                    if sys.platform == "win32":
                        import ctypes
                        from ctypes import wintypes
                        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                        kernel.OpenProcess.restype = wintypes.HANDLE
                        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                        handle = kernel.OpenProcess(0x00100000, False, worker_pid)
                        if handle:
                            try:
                                assert kernel.WaitForSingleObject(handle, 0) == 0
                            finally:
                                kernel.CloseHandle(handle)
                    else:
                        with pytest.raises(ProcessLookupError):
                            os.kill(worker_pid, 0)
                    assert not staging.exists()
                    factory = create_session_factory(data / "data" / "autoflow.sqlite3")
                    try:
                        saved = SqlAlchemyKernelOperationRepository(factory).get(operation["id"])
                        assert saved is not None and saved.state == "cancelled"
                    finally:
                        factory.dispose()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
