"""Guarded real Android management smoke entry point.

The command only mutates a device created in the supplied isolated data
directory and requires an explicit authorization flag before doing so.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the guarded Android management smoke test")
    parser.add_argument("--workspace", required=True, type=Path, help="isolated workspace for generated resources")
    parser.add_argument("--allow-device-mutation", action="store_true", help="explicitly authorize device mutation")
    parser.add_argument("--device-id", action="append", default=[], help="device created by this smoke run")
    parser.add_argument("--scrcpy-archive", type=Path, help="verified local scrcpy archive")
    args = parser.parse_args(argv)
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required before any device mutation")
    return args


async def run_smoke(args: argparse.Namespace) -> dict:
    from autoflow.bootstrap.android_prepare import prepare
    from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
    from autoflow.infrastructure.database.session import (
        create_session_factory,
        migrate_database,
    )
    from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
    from autoflow.infrastructure.filesystem.paths import AppPaths
    from autoflow.providers.android.mac_runtime import MacAndroidRuntime

    data_dir = args.workspace.resolve()
    paths = AppPaths.from_data_dir(data_dir)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    repo = SqlAlchemyDeviceRepository(sessions)
    try:
        existing = [item for item in repo.list() if not item.get("deleted")]
        if existing and not args.device_id:
            raise RuntimeError("isolated workspace already contains a live device; pass --device-id only to resume an owned run")
        if args.device_id:
            wanted = {str(UUID(value)) for value in args.device_id}
            devices = [item for item in existing if item.get("deviceId") in wanted]
            if len(devices) != len(wanted):
                raise RuntimeError("--device-id must refer to devices already registered in this isolated workspace")
            if len(devices) != 1:
                raise RuntimeError("the smoke run accepts exactly one device")
            device = devices[0]
        else:
            device = await prepare(data_dir, args.scrcpy_archive, False)
        runtime = MacAndroidRuntime(android_runtime_root(), paths.workspace)
        runtime.lock()
        stages: list[str] = []
        save = lambda: repo.save(device)
        try:
            await runtime.connect(device, save)
            applications = await runtime.app_info()
            screenshot = await runtime.command("android_screenshot", {}, 15)
            await runtime.command("android_key", {"key": "HOME"}, 15)
            await runtime.disconnect()

            await runtime.manage(device, {"action": "stop", "deleteData": False}, stages.append, save)
            await runtime.manage(device, {"action": "start", "deleteData": False}, stages.append, save)
            await runtime.connect(device, save)
            resumed = await runtime.app_info()
            await runtime.disconnect()

            await runtime.manage(device, {"action": "delete", "deleteData": True}, stages.append, save)
            repo.save(device)
            return {
                "status": "passed",
                "deviceId": device["deviceId"],
                "workspaceId": device["workspaceId"],
                "applicationCount": len(applications.get("applications", [])),
                "resumedApplicationCount": len(resumed.get("applications", [])),
                "screenshotBytes": len(screenshot),
                "stages": stages,
                "cleanup": {"deleted": bool(device.get("deleted")), "dataRetained": bool(device.get("dataRetained"))},
            }
        except BaseException:
            await runtime.disconnect()
            raise
        finally:
            runtime.unlock()
    finally:
        sessions.dispose()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = asyncio.run(run_smoke(args))
    except Exception as error:  # noqa: BLE001 - the CLI must report blocked/failed without a false pass.
        print(json.dumps({"status": "blocked", "workspace": str(args.workspace), "message": str(error)[:480]}, ensure_ascii=False), file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
