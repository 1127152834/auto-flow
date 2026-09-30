import pytest
from fastapi.testclient import TestClient

from autoflow.infrastructure.observability import LoopLagMonitor
from tests.contract.test_settings_dashboard import _app


def test_sidecar_runs_one_loop_lag_monitor_for_its_lifetime(tmp_path):
    app = _app(tmp_path)
    with TestClient(app):
        monitor = app.state.loop_lag
        assert isinstance(monitor, LoopLagMonitor)
        assert monitor.running
    assert not monitor.running


def test_monitor_stops_when_another_shutdown_hook_fails(tmp_path, monkeypatch):
    app = _app(tmp_path)

    original_shutdown = app.state.studio_retention.shutdown

    async def fail():
        await original_shutdown()
        raise RuntimeError("shutdown failure")

    with pytest.raises(RuntimeError, match="shutdown failure"), TestClient(app):
        monitor = app.state.loop_lag
        monkeypatch.setattr(app.state.studio_retention, "shutdown", fail)
    assert not monitor.running
