from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

FAKE_WRAPPER = '''
import os
from pathlib import Path
from types import SimpleNamespace

IMPORTED_CACHE = os.environ.get("CLOAKBROWSER_CACHE_DIR")
if not IMPORTED_CACHE:
    raise RuntimeError("wrapper imported before task cache was set")

def validate_license(key):
    assert key == "private-test-key"
    print(key)
    return SimpleNamespace(valid=True, plan="pro", expires=None)

def ensure_binary(*, license_key, browser_version, release_channel):
    assert release_channel == "stable"
    print(license_key)
    suffix = "-pro" if license_key else ""
    executable = Path(IMPORTED_CACHE) / f"chromium-{browser_version}{suffix}" / "chrome.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"browser")
    return str(executable)
'''

FAKE_LICENSE = '''
from types import SimpleNamespace
from . import IMPORTED_CACHE

assert IMPORTED_CACHE

def get_pro_latest_release(channel):
    if channel == "stable":
        return SimpleNamespace(version="146.0.7680.80", resolved_channel=channel)
    return None

def get_session_seats(key):
    assert key == "private-test-key"
    return SimpleNamespace(active=1, limit=2)
'''


@pytest.fixture
def fake_wrapper(tmp_path: Path) -> Path:
    package = tmp_path / "fake-wrapper" / "cloakbrowser"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(textwrap.dedent(FAKE_WRAPPER), encoding="utf-8")
    (package / "license.py").write_text(textwrap.dedent(FAKE_LICENSE), encoding="utf-8")
    return package.parent


def _run_worker(fake_wrapper: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    source = Path(__file__).parents[2] / "src"
    env = os.environ.copy()
    env.pop("CLOAKBROWSER_CACHE_DIR", None)
    env["PYTHONPATH"] = os.pathsep.join((str(source), str(fake_wrapper)))
    return subprocess.run(
        [sys.executable, "-m", "autoflow", "--kernel-worker"],
        input=json.dumps(payload) + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
        timeout=5,
    )


@pytest.mark.parametrize("command", ["catalog", "license", "download"])
def test_worker_sets_task_cache_before_each_wrapper_command_and_writes_only_json(
    tmp_path: Path, fake_wrapper: Path, command: str
) -> None:
    cache = tmp_path / "staging" / command
    payload: dict[str, object] = {"command": command, "cacheDir": str(cache)}
    if command in {"license", "download"}:
        payload["licenseKey"] = "private-test-key"
    if command == "download":
        payload.update(
            requestedVersion="146.0.7680.80",
            releaseChannel="stable",
            edition="licensed",
        )

    result = _run_worker(fake_wrapper, payload)
    messages = [json.loads(line) for line in result.stdout.splitlines()]

    assert result.returncode == 0
    assert result.stderr == ""
    assert messages
    assert "private-test-key" not in result.stdout


def test_worker_rejects_arbitrary_commands_without_echoing_sensitive_input(
    tmp_path: Path, fake_wrapper: Path
) -> None:
    result = _run_worker(
        fake_wrapper,
        {
            "command": "shell",
            "cacheDir": str(tmp_path / "staging"),
            "licenseKey": "private-test-key",
        },
    )

    assert result.returncode == 1
    assert json.loads(result.stdout) == {"type": "error", "error": "Kernel worker failed"}
    assert "private-test-key" not in result.stdout + result.stderr
