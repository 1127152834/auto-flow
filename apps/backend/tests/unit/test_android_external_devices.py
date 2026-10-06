from __future__ import annotations

import sys
import textwrap

import pytest

from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android.external_devices import (
    list_external_devices,
    parse_adb_devices,
)


def test_parse_adb_devices_basic():
    """Parse basic adb devices output with mixed states."""
    output = textwrap.dedent("""
        List of devices attached
        emulator-5554 device product:sdk_gphone64 model:sdk_gphone64_arm64
        127.0.0.1:5556 device
        R58M unauthorized

    """).strip()

    result = parse_adb_devices(output)

    assert len(result) == 3
    assert result[0] == {"serial": "emulator-5554", "state": "device", "model": "sdk_gphone64_arm64", "product": "sdk_gphone64"}
    assert result[1] == {"serial": "127.0.0.1:5556", "state": "device", "model": None, "product": None}
    assert result[2] == {"serial": "R58M", "state": "unauthorized", "model": None, "product": None}


def test_parse_adb_devices_skips_daemon_lines():
    """Skip daemon lines starting with *."""
    output = textwrap.dedent("""
        List of devices attached
        * daemon not running; starting now at tcp:5037
        * daemon started successfully
        emulator-5554 device
    """).strip()

    result = parse_adb_devices(output)

    assert len(result) == 1
    assert result[0]["serial"] == "emulator-5554"


def test_parse_adb_devices_skips_header():
    """Skip the 'List of devices attached' header."""
    output = "List of devices attached\nFAKE001 device"
    result = parse_adb_devices(output)

    assert len(result) == 1
    assert result[0]["serial"] == "FAKE001"


def test_parse_adb_devices_empty():
    """Handle empty output (just header)."""
    output = "List of devices attached\n"
    result = parse_adb_devices(output)

    assert result == []


def test_parse_adb_devices_unknown_state():
    """Unknown states pass through verbatim."""
    output = "List of devices attached\nDEV001 recovery\nDEV002 sideload"
    result = parse_adb_devices(output)

    assert len(result) == 2
    assert result[0]["state"] == "recovery"
    assert result[1]["state"] == "sideload"


@pytest.mark.asyncio
async def test_list_external_devices_filters_managed(tmp_path):
    """Filter out managed serials and return external devices."""
    fake_adb = tmp_path / "fake_adb.py"
    fake_adb.write_text(textwrap.dedent("""
        import sys
        print("List of devices attached")
        print("emulator-5554 device product:sdk_gphone64 model:sdk_gphone64_arm64")
        print("127.0.0.1:5556 device")
        print("R58M unauthorized")
    """))

    managed = {"127.0.0.1:5556"}
    # Pass command as [python_exe, script_path] to invoke the fake adb
    result = await list_external_devices(managed, adb=[sys.executable, str(fake_adb)])

    assert len(result) == 2
    assert result[0]["serial"] == "emulator-5554"
    assert result[1]["serial"] == "R58M"


@pytest.mark.asyncio
async def test_list_external_devices_adb_missing(tmp_path):
    """Raise AndroidError when adb is not found."""
    with pytest.raises(AndroidError) as exc:
        await list_external_devices(set(), adb="/nonexistent/adb")

    assert exc.value.code == "ANDROID_ADB_MISSING"
    assert exc.value.status == 503


@pytest.mark.asyncio
async def test_list_external_devices_spawn_error_keeps_the_reason(monkeypatch):
    """Any other spawn failure (e.g. PermissionError) is a 502 carrying the OS reason, not a bare 500."""

    async def refuse(*_args, **_kwargs):
        raise PermissionError(13, "拒绝访问")

    monkeypatch.setattr("asyncio.create_subprocess_exec", refuse)
    with pytest.raises(AndroidError) as exc:
        await list_external_devices(set(), adb="adb")

    assert (exc.value.code, exc.value.status) == ("ANDROID_ADB_FAILED", 502)
    assert "拒绝访问" in exc.value.message


@pytest.mark.asyncio
async def test_list_external_devices_adb_timeout(tmp_path):
    """Raise AndroidError on adb timeout."""
    fake_adb = tmp_path / "slow_adb.py"
    fake_adb.write_text(textwrap.dedent("""
        import time
        time.sleep(10)
    """))

    with pytest.raises(AndroidError) as exc:
        await list_external_devices(set(), adb=[sys.executable, str(fake_adb)])

    assert exc.value.code == "ANDROID_ADB_TIMEOUT"
    assert exc.value.status == 504


@pytest.mark.asyncio
async def test_list_external_devices_adb_fails(tmp_path):
    """Raise AndroidError when adb exits with non-zero code."""
    fake_adb = tmp_path / "fail_adb.py"
    fake_adb.write_text(textwrap.dedent("""
        import sys
        print("error: device not found", file=sys.stderr)
        sys.exit(1)
    """))

    with pytest.raises(AndroidError) as exc:
        await list_external_devices(set(), adb=[sys.executable, str(fake_adb)])

    assert exc.value.code == "ANDROID_ADB_FAILED"
    assert exc.value.status == 502
    assert "device not found" in exc.value.message


@pytest.mark.asyncio
async def test_list_external_devices_no_managed_serials(tmp_path):
    """When no serials are managed, return all devices."""
    fake_adb = tmp_path / "fake_adb.py"
    fake_adb.write_text(textwrap.dedent("""
        import sys
        print("List of devices attached")
        print("DEV001 device")
        print("DEV002 offline")
    """))

    result = await list_external_devices(set(), adb=[sys.executable, str(fake_adb)])

    assert len(result) == 2
    assert result[0]["serial"] == "DEV001"
    assert result[1]["serial"] == "DEV002"


@pytest.mark.asyncio
async def test_list_external_devices_empty_result(tmp_path):
    """Return empty list when adb has no devices."""
    fake_adb = tmp_path / "empty_adb.py"
    fake_adb.write_text("print('List of devices attached')")

    result = await list_external_devices(set(), adb=[sys.executable, str(fake_adb)])

    assert result == []
