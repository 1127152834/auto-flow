import sys
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from autoflow.__main__ import main


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10"])
def test_main_rejects_non_loopback_host(monkeypatch, host):
    monkeypatch.setattr(
        sys,
        "argv",
        ["autoflow", "--host", host, "--instance-id", "test", "--data-dir", "/tmp/autoflow-test"],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_main_requires_explicit_data_dir(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["autoflow", "--instance-id", "test"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_main_dispatches_workflow_worker_without_starting_http(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["autoflow", "--workflow-worker"])
    monkeypatch.setattr(
        "autoflow.bootstrap.workflow_worker.workflow_worker_main", lambda: 17
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 17


def test_main_does_not_print_ready_when_app_creation_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["autoflow", "--instance-id", "test", "--data-dir", str(tmp_path)],
    )
    monkeypatch.setattr("autoflow.__main__.create_app", lambda _settings: (_ for _ in ()).throw(RuntimeError("migration failed")))

    with pytest.raises(RuntimeError, match="migration failed"):
        main()

    assert "AUTOFLOW_READY" not in capsys.readouterr().out


def test_app_shutdown_stops_kernel_workers(monkeypatch, tmp_path):
    from autoflow.bootstrap.app import create_app
    from autoflow.bootstrap.config import Settings

    close_proxies = Mock()
    proxy_runtime = Mock(resolve_profile=AsyncMock(), close=close_proxies)
    monkeypatch.setattr(
        "autoflow.bootstrap.app.configure_proxy_management",
        lambda _app, _database, _references: proxy_runtime,
    )
    app = create_app(Settings(data_dir=str(tmp_path), instance_id="test"))
    shutdown = AsyncMock()
    monkeypatch.setattr(app.state.kernel_worker_manager, "shutdown", shutdown)

    with TestClient(app):
        pass

    shutdown.assert_awaited_once_with()
    close_proxies.assert_called_once_with()
