import sys

import pytest

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
