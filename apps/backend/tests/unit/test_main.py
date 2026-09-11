import sys

import pytest

from autoflow.__main__ import main


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10"])
def test_main_rejects_non_loopback_host(monkeypatch, host):
    monkeypatch.setattr(sys, "argv", ["autoflow", "--host", host, "--instance-id", "test"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
