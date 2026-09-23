"""Opt-in real APK install interruption while the guest package command is alive."""

import argparse
import asyncio
import hashlib
import json
import os
import runpy
import signal
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.application.android.apk import parse_apk
from autoflow.bootstrap.android import android_service
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.infrastructure.process.browser_processes import process_birth
from autoflow.providers.android.mac_runtime import VM, docker, package_inventory
from autoflow.providers.android.management import verify

HELPERS = runpy.run_path(str(Path(__file__).with_name("restore-interruption-smoke.py")))
expect = HELPERS["expect"]

# Observe the real package command, then stop only that client to hold the fault
# boundary. PackageManager itself remains running. No result/receipt is injected.
WATCH = r'''
echo watching
while :; do
  processes=$(ps -A -o PID,ARGS)
  while read -r pid cmd; do
    [ "$pid" = "$$" ] && continue
    case "$cmd" in
      *"package install -r /data/local/tmp/autoflow-apk-"*)
        for apk in /data/local/tmp/autoflow-apk-*.apk; do
          [ -f "$apk" ] || continue
          size=$(stat -c %s "$apk")
          birth=$(cut -d ' ' -f22 "/proc/$pid/stat")
          printf '%s %s %s %s\n' "$pid" "$birth" "$size" "$apk" > "$1"
          kill -STOP "$pid" || exit 2
          cat "$1"
          exit
        done
      ;;
    esac
  done <<EOF
$processes
EOF
  sleep .02
done
'''


async def resume_package(device, watch_file):
    await docker("exec", device["containerId"], "sh", "-c", '''
if [ -f "$1" ]; then
 read pid birth size apk < "$1"
 if [ -f "/proc/$pid/stat" ] && [ "$(cut -d ' ' -f22 /proc/$pid/stat)" = "$birth" ]; then
  kill -CONT "$pid"
 fi
 rm -f "$1"
fi
''', "sh", watch_file)


async def exercise(apk):
    content = apk.read_bytes()
    metadata = parse_apk(content)
    workspace = Path(tempfile.mkdtemp(prefix="autoflow-app-interrupt-"))
    paths = AppPaths.from_data_dir(workspace)
    paths.database.parent.mkdir(parents=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    devices = android_service(sessions, paths.workspace)
    resources = AndroidResourceRepository(sessions)
    report = {"workspace": str(workspace), "apk": metadata, "apkSha256": hashlib.sha256(content).hexdigest(), "cases": [], "status": "started"}
    process = client = monitor = request = None
    scenarios_passed = False
    owned = []
    watch_file = "/data/local/tmp/autoflow-qa-paused-" + uuid4().hex
    try:
        process, client = await HELPERS["start_server"](workspace)
        image = json.loads(await docker("image", "inspect", "redroid/redroid:13.0.0_64only-latest"))[0]["Id"]
        report["imageId"] = image
        expect(await client.post("/api/v1/android/management/images", json={"id": image, "name": "Install interruption QA", "reference": "redroid/redroid:13.0.0_64only-latest"}), 201)
        for mode in ("adb_disconnect", "http_sigkill"):
            identifier = str(uuid4())
            created = expect(await client.post("/api/v1/android/devices", json={"deviceId": identifier, "name": "APK fault " + mode, "imageId": image, "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "start": True}), 202)
            owned.append(identifier)
            device = await HELPERS["wait_device"](devices.repository, identifier, created["operation"]["id"])
            assert device["androidStatus"] == "ready"
            session = expect(await client.post("/api/v1/android/sessions", json={"requestId": str(uuid4()), "deviceId": identifier, "clientSessionId": str(uuid4()), "access": "manual"}), 200)
            endpoint = f"/api/v1/android/sessions/{session['id']}/apps/install"
            expect(await client.post(endpoint, params={"generation": session["generation"], "requestId": str(uuid4())}, content=content, headers={"content-type": "application/vnd.android.package-archive"}), 200)
            app_data = "/data/user/0/" + metadata["packageName"]
            probe = app_data + "/files/autoflow-app-fault-proof"
            await docker("exec", device["containerId"], "sh", "-c", '''
owner=$(stat -c %u:%g "$1") || exit
mkdir -p "$1/files" && printf %s "$2" > "$3" && chown "$owner" "$1/files" "$3"
''', "sh", app_data, identifier, probe)
            monitor = await asyncio.create_subprocess_exec("limactl", "shell", "--workdir=/tmp", VM, "sudo", "docker", "exec", device["containerId"], "sh", "-c", WATCH, "sh", watch_file, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
            assert await asyncio.wait_for(monitor.stdout.readline(), 10) == b"watching\n"
            request_id = str(uuid4())
            params = {"generation": session["generation"], "requestId": request_id}
            request = asyncio.create_task(client.post(endpoint, params=params, content=content, headers={"content-type": "application/vnd.android.package-archive"}))
            observed = (await asyncio.wait_for(monitor.stdout.readline(), 90)).decode().split()
            assert len(observed) == 4 and int(observed[2]) == len(content), observed
            assert await monitor.wait() == 0
            monitor = None
            device = devices.repository.get(identifier)
            marker = device["pendingCommand"]
            await docker("exec", device["containerId"], "test", "!", "-e", marker)
            assert not request.done(), "Install completed before interruption"
            await devices.runtime.inspect(device)
            case = {"mode": mode, "deviceId": identifier, "sessionId": session["id"], "requestId": request_id, "generation": session["generation"], "guestPackagePid": int(observed[0]), "guestProcessBirth": observed[1], "uploadedBytes": int(observed[2]), "completionAbsentBeforeFault": True}
            report["cases"].append(case)
            if mode == "adb_disconnect":
                tunnel = device["processes"]["tunnel"]
                assert tunnel["birth"] and process_birth(tunnel["pid"]) == tunnel["birth"]
                case["tunnelPid"] = tunnel["pid"]
                os.kill(tunnel["pid"], signal.SIGTERM)
            else:
                case["killedProcessGroups"] = await HELPERS["kill_owned_tree"](process)
            await resume_package(device, watch_file)
            response = (await asyncio.gather(request, return_exceptions=True))[0]
            case["httpResult"] = response.status_code if hasattr(response, "status_code") else type(response).__name__
            assert case["httpResult"] != 200, case
            request = None
            saved = resources.get("session", session["id"])["appReceipts"][request_id]
            assert saved["state"] in {"running", "needs_verification"}, saved
            case["receiptAfterFault"] = saved["state"]
            await HELPERS["stop_server"](process, client)
            process = client = None
            process, client = await HELPERS["start_server"](workspace)
            replay = await client.post(endpoint, params=params, content=content, headers={"content-type": "application/vnd.android.package-archive"})
            assert replay.status_code in {409, 410, 503}
            case["replayStatus"] = replay.status_code
            verification = await client.post(f"/api/v1/android/sessions/{session['id']}/apps/verify", json={"requestId": request_id, "generation": session["generation"]})
            case["verifyStatus"] = verification.status_code
            case["receiptAfterVerify"] = resources.get("session", session["id"])["appReceipts"][request_id]["state"]
            assert verification.status_code in {200, 422, 503}, verification.text
            if verification.status_code == 503:
                assert case["receiptAfterVerify"] == "needs_verification"
                denied = await client.post("/api/v1/android/sessions", json={"requestId": str(uuid4()), "deviceId": identifier, "clientSessionId": str(uuid4()), "access": "manual"})
                assert denied.status_code == 409, denied.text
                case["unknownControlBlocked"] = True
            else:
                assert case["receiptAfterVerify"] == ("succeeded" if verification.status_code == 200 else "failed")
                recovered = await HELPERS["operate"](client, devices.repository, identifier, "recover")
                assert recovered["control"] == "idle"
                case["terminalRecoveryIdle"] = True
            assert (await docker("exec", device["containerId"], "cat", probe)).decode() == identifier
            case["sourceProbeUnchanged"] = True
            case["applicationDataUnchanged"] = True
            installed = package_inventory(await docker("exec", device["containerId"], "pm", "list", "packages", "--show-versioncode"))
            assert installed.get(metadata["packageName"]) == metadata["versionCode"]
            case["installedVersionAfterFault"] = installed[metadata["packageName"]]
            # This stage only proves the reported outcome, never upgrades unknown.
            (workspace / "result.json").write_text(json.dumps(report, indent=2))
        scenarios_passed = True
    finally:
        if monitor and monitor.returncode is None:
            os.killpg(monitor.pid, signal.SIGKILL)
            await monitor.wait()
        if request and not request.done():
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)
        for identifier in owned:
            try:
                device = devices.repository.get(identifier)
                await resume_package(device, watch_file)
            except (AndroidError, OSError, TimeoutError) as error:
                report.setdefault("resumeErrors", []).append(type(error).__name__)
        try:
            if process:
                try:
                    await HELPERS["stop_server"](process, client)
                except TimeoutError:
                    report["shutdownTimeout"] = True
            # Fixture teardown is distinct from product recovery. Remove only the
            # freshly-created immutable IDs after production ownership checks.
            for identifier in owned:
                device = devices.repository.get(identifier)
                containers, volumes = await verify(device, devices.runtime.workspace_id)
                for container in containers:
                    await docker("rm", "-f", container["Id"])
                for volume in volumes:
                    await docker("volume", "rm", volume["Name"])
                assert (await devices.runtime.verify_deleted(device))["androidStatus"] == "missing"
            report["ownedContainersVolumesRemoved"] = True
            if scenarios_passed:
                report["status"] = "passed"
        finally:
            sessions.dispose()
            (workspace / "result.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-device-mutation", action="store_true")
    parser.add_argument("--apk", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required")
    asyncio.run(exercise(args.apk))
