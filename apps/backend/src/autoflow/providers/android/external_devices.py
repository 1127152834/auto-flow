"""External device discovery via adb."""

from __future__ import annotations

import asyncio
import shutil

from autoflow.domain.android.ports import AndroidError


def parse_adb_devices(output: str) -> list[dict[str, str | None]]:
    """Parse adb devices -l output into device records.

    Each record has: serial, state, model, product.
    Skips header, blank lines, and daemon lines starting with *.
    Unknown states pass through verbatim.
    """
    devices = []

    for line in output.splitlines():
        line = line.strip()

        # Skip empty lines, header, and daemon lines
        if not line or line == "List of devices attached" or line.startswith("*"):
            continue

        tokens = line.split()
        if len(tokens) < 2:
            continue

        serial = tokens[0]
        state = tokens[1]

        # Extract model and product from key:value tokens
        model = None
        product = None
        for token in tokens[2:]:
            if token.startswith("model:"):
                model = token[6:]
            elif token.startswith("product:"):
                product = token[8:]

        devices.append({
            "serial": serial,
            "state": state,
            "model": model,
            "product": product,
        })

    return devices


async def list_external_devices(
    managed_serials: set[str],
    adb: str | list[str] | None = None,
) -> list[dict[str, str | None]]:
    """List external devices via adb, excluding managed ones.

    Args:
        managed_serials: Set of device serials to exclude
        adb: Path to adb executable (str), command as list (for testing), or None to use shutil.which("adb")

    Returns:
        List of device dicts with serial, state, model, product

    Raises:
        AndroidError with code ANDROID_ADB_MISSING (503) if adb not found
        AndroidError with code ANDROID_ADB_TIMEOUT (504) if adb times out
        AndroidError with code ANDROID_ADB_FAILED (502) if adb exits non-zero
    """
    # Resolve adb command
    if adb is None:
        adb_path = shutil.which("adb")
        if not adb_path:
            raise AndroidError("ANDROID_ADB_MISSING", "未找到 adb", 503)
        cmd = [adb_path]
    elif isinstance(adb, list):
        cmd = adb
    else:
        cmd = [adb]

    # Run adb devices -l with 5 second timeout
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, "devices", "-l",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    except FileNotFoundError:
        raise AndroidError("ANDROID_ADB_MISSING", "未找到 adb", 503)
    except TimeoutError:
        # Kill the process and raise timeout error
        proc.kill()
        try:
            await proc.wait()
        except OSError:
            pass
        raise AndroidError("ANDROID_ADB_TIMEOUT", "adb 无响应", 504)
    except OSError as exc:  # after TimeoutError (an OSError subclass); e.g. PermissionError: keep the OS reason visible
        raise AndroidError("ANDROID_ADB_FAILED", f"无法启动 adb：{exc.strerror or exc}", 502) from None

    # Check exit code
    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        # Use last line of stderr for error message
        error_msg = stderr_text.split("\n")[-1] if stderr_text else "adb failed"
        raise AndroidError("ANDROID_ADB_FAILED", error_msg, 502)

    # Parse output
    output = stdout.decode("utf-8", errors="replace")
    all_devices = parse_adb_devices(output)

    # Filter out managed serials
    external = [d for d in all_devices if d["serial"] not in managed_serials]

    return external
