from pathlib import Path

import pytest

from autoflow.providers.browser.persistent_context import (
    launch_persistent_instance,
    persistent_launch_kwargs,
)

COMMAND = {
    "fingerprintSeed": 31415,
    "expertArgs": ["--disable-gpu"],
    "humanPreset": "default",
    "browserVersion": "146.0.1",
    "releaseChannel": "stable",
    "geoip": False,
    "humanize": False,
}


def test_persistent_kwargs_use_official_user_data_dir(tmp_path):
    directory = tmp_path / "instance"
    executable = tmp_path / "Chromium"
    executable.write_text("synthetic")
    options = persistent_launch_kwargs(
        directory, {**COMMAND, "executablePath": str(executable)}, headless=True
    )
    assert options["user_data_dir"] == str(directory.resolve())
    assert "executable_path" not in options
    assert options["headless"] is True
    assert "--user-data-dir" not in " ".join(options["args"])
    assert any(arg.startswith("--fingerprint=") for arg in options["args"])


def test_persistent_kwargs_reject_user_data_dir_expert_arg(tmp_path):
    with pytest.raises(ValueError, match="reserved"):
        persistent_launch_kwargs(
            tmp_path,
            {**COMMAND, "expertArgs": ["--user-data-dir=/tmp/stolen"]},
            headless=True,
        )


@pytest.mark.asyncio
async def test_launch_persistent_instance_calls_official_api(tmp_path, monkeypatch):
    launched = {}

    async def fake_launch(**kwargs):
        launched.update(kwargs)
        return "context"

    monkeypatch.setattr(
        "cloakbrowser.launch_persistent_context_async",
        fake_launch,
        raising=False,
    )
    import cloakbrowser

    monkeypatch.setattr(cloakbrowser, "launch_persistent_context_async", fake_launch)
    result = await launch_persistent_instance(tmp_path / "work", COMMAND, headless=True)
    assert result == "context"
    assert Path(launched["user_data_dir"]).name == "work"
    assert "--user-data-dir" not in " ".join(launched["args"])
