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
