#!/usr/bin/env python3
"""Record ADB shell/Magisk evidence from the WSL/Linux host; application root stays unverified."""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, build_opener


def execute(argv, timeout=20):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"command": argv, "exit_code": completed.returncode,
                "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
    except subprocess.TimeoutExpired as error:
        return {"command": argv, "exit_code": None, "error": f"Timed out after {timeout}s",
                "stdout": (error.stdout or b"").decode(errors="replace"),
                "stderr": (error.stderr or b"").decode(errors="replace")}


def inspect_root(api, instance_id):
    opener = build_opener(ProxyHandler({})) if urlsplit(api).hostname in ("localhost", "127.0.0.1", "::1") else build_opener()
    with opener.open(api.rstrip("/") + "/api/instances/" + quote(instance_id, safe=""), timeout=30) as response:
        instance = json.load(response)
    address = instance.get("adb_address") or ""
    if not re.fullmatch(r"127\.0\.0\.1:([1-9][0-9]{0,4})", address) or int(address.rsplit(":", 1)[1]) > 65535:
        raise ValueError("Expected the Demo's published localhost ADB address; run on the actual WSL/Linux Docker host")
    if instance.get("android_status") != "ready":
        raise ValueError("Android must be ready before checking root")
    report = {"instance_id": instance_id, "image": instance["image"], "image_id": instance["image_id"],
              "adb_address": address, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "application_root": {"status": "unverified", "reason": "Requires a separate APK requesting root; shell UID is not app permission"},
              "checks": {}, "transport_ok": False}
    existing = execute(["adb", "devices"])
    already_connected = any(line.split()[0] == address for line in existing["stdout"].splitlines() if line.split())
    report["checks"]["connect"] = execute(["adb", "connect", address])
    adb = ["adb", "-s", address]
    try:
        report["checks"]["shell_before"] = execute(adb + ["shell", "id"])
        report["checks"]["adb_root"] = execute(adb + ["root"])
        report["checks"]["wait_after_root"] = execute(adb + ["wait-for-device"], timeout=30)
        report["checks"]["shell_after"] = execute(adb + ["shell", "id"])
        report["checks"]["magisk_version"] = execute(adb + ["shell", "magisk", "-v"])
        report["checks"]["shell_su"] = execute(adb + ["shell", "su", "-c", "id"])
        after = report["checks"]["shell_after"]
        report["transport_ok"] = after["exit_code"] == 0 and "uid=" in after["stdout"]
        report["adb_shell_root"] = {"status": "pass" if after["exit_code"] == 0 and "uid=0(" in after["stdout"] else "not_observed"}
    finally:
        if not already_connected:
            report["checks"]["disconnect"] = execute(["adb", "disconnect", address])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, default=Path(".data/root-check.json"))
    args = parser.parse_args()
    try:
        if not shutil.which("adb"):
            raise RuntimeError("adb is missing; install android-tools-adb on the WSL/Linux host")
        result = inspect_root(args.api, args.instance_id)
    except Exception as error:
        result = {"instance_id": args.instance_id, "transport_ok": False, "error": str(error), "application_root": {"status": "unverified"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Unsupported root is a measured result; transport/script failure is a failing exit status.
    return 0 if result["transport_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
