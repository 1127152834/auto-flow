"""Real source-worker failure/cleanup smoke; run with the backend's Python environment.

Example:
  PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python scripts/smoke-workflow-worker.py \
    --kernel-directory '/absolute/path/to/chromium-145.0.7632.109.2'

This deliberately signals only worker groups created in its own temporary workspace.
The installed kernel is cloned, never modified. Windows signal scenarios remain untested.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.run_validation import prepare_run
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager

ROOT = Path(__file__).resolve().parents[1]
PAGE = b'''<!doctype html><meta charset="utf-8"><title>AutoFlow worker cleanup fixture</title>
<button id="popup" onclick="window.open('/popup')">Open popup</button><p id="ready">ready</p>'''
POPUP = b'''<!doctype html><title>AutoFlow owned popup</title>
<button id="close" onclick="window.close()">Close this page</button>'''
FONT_PAGE = b'''<!doctype html><style>@font-face{font-family:Pending;src:url('/font-hang')}
body{font-family:Pending}</style><p>Screenshot must wait for this real pending font.</p>'''


def process_table():
    rows = subprocess.check_output(
        ["ps", "-ax", "-o", "pid=,ppid=,pgid=,stat=,command="], text=True,
    ).splitlines()
    return [dict(zip(("pid", "ppid", "pgid", "stat", "command"), row.split(None, 4), strict=True)) for row in rows]


def group_rows(group):
    return [row for row in process_table() if int(row["pgid"]) == group]


async def until(check, label, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        await asyncio.sleep(0.015)
    raise AssertionError(f"Timed out: {label}")


async def gone(group, captured, browser_prefix=None):
    await until(
        lambda: not group_rows(group) and not any(
            int(row["pid"]) in captured or (browser_prefix and row["command"].startswith(browser_prefix))
            for row in process_table()
        ),
        "all owned worker/browser/driver processes exited", 10,
    )
    return {"capturedProcessCount": len(captured), "remainingGroupProcesses": 0, "remainingCapturedProcesses": 0, "remainingOwnedBrowserProcesses": 0}


def workflow(steps):
    catalog = {item["type"]: item for item in node_catalog()}
    nodes = [
        {"id": f"n{i}", "type": kind, "label": kind,
         "config": {**catalog[kind]["defaultConfig"], "timeoutSeconds": 30, **config}}
        for i, (kind, config) in enumerate(steps)
    ]
    document = {
        "id": str(uuid4()), "name": "Worker cleanup smoke", "schemaVersion": 1,
        "nodes": nodes, "variables": [],
        "edges": [{"id": f"e{i}", "source": nodes[i]["id"], "target": node["id"],
                   "sourceHandle": "out", "targetHandle": "in"} for i, node in enumerate(nodes[1:])],
    }
    layout = {"nodes": {n["id"]: {"x": i * 240, "y": 0} for i, n in enumerate(nodes)},
              "viewport": {"x": 0, "y": 0, "zoom": 1}}
    return document, layout


class Fixture:
    def __init__(self):
        self.requests: list[str] = []
        self.release = Event()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fixture.requests.append(self.path)
                if self.path in {"/hang", "/font-hang"}:
                    fixture.release.wait(60)
                    return
                data = POPUP if self.path == "/popup" else FONT_PAGE if self.path == "/font-page" else PAGE
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


def http_json(base, token, path, body=None):
    request = Request(
        base + "/api/v1/" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"x-autoflow-token": token, "Content-Type": "application/json"},
    )
    with build_opener(ProxyHandler({})).open(request, timeout=10) as response:
        return json.load(response)


async def smoke(args, report):
    if os.name != "posix":
        report["limitations"].append("POSIX signal/process inspection scenarios are not implemented for Windows")
        return
    fixture = Fixture()
    groups: set[int] = set()
    sidecar = None
    managers = []
    source = args.kernel_directory.resolve(strict=True)
    version = source.name.removeprefix("chromium-")
    report["kernelVersion"] = version
    with tempfile.TemporaryDirectory(prefix="autoflow-m2-worker-") as temporary:
        workspace = Path(temporary).resolve()
        copied = workspace / "data" / "kernels" / source.name
        copied.parent.mkdir(parents=True)
        if sys.platform == "darwin":
            await asyncio.to_thread(subprocess.run, ["cp", "-cR", str(source), str(copied)], check=True)
            executable = copied / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        else:
            shutil.copytree(source, copied, symlinks=True)
            executable = copied / "chrome"
        assert executable.is_file()

        def tree_rows(pid):
            rows = process_table()
            owned = {pid} | {int(row["pid"]) for row in rows if row["command"].startswith(str(copied))}
            previous = set()
            while previous != owned:
                previous = owned.copy()
                owned.update(int(row["pid"]) for row in rows if int(row["ppid"]) in owned)
            selected = [row for row in rows if int(row["pid"]) in owned]
            groups.update(int(row["pgid"]) for row in selected)
            return selected
        now = datetime.now(UTC)
        saved = Profile("smoke-profile", ProfileSpec.from_values({
            "name": "Isolated worker smoke", "browser_version": version,
            "headless": True, "locale": "ja-JP", "timezone": "Asia/Tokyo",
            "start_url": fixture.url + "/must-not-open",
        }), 12345, now, now)
        env = {**os.environ, "PYTHONPATH": str(ROOT / "apps/backend/src")}
        env.pop("CLOAKBROWSER_LICENSE_KEY", None)

        def new_manager():
            manager = WorkflowWorkerManager(workspace / "temp", workspace / "runs", worker_env=env)
            managers.append(manager)
            return manager

        async def begin(steps):
            manager = new_manager()
            run_id, events = str(uuid4()), []
            document, layout = workflow(steps)

            async def emit(event):
                events.append(event)

            task = asyncio.create_task(manager.execute(
                run_id, prepare_run(document, layout), saved, executable, None, None, emit,
            ))
            row = await until(
                lambda: next((row for row in process_table() if int(row["ppid"]) == os.getpid()
                              and "--workflow-worker" in row["command"]), None),
                "owned source worker spawn",
            )
            group = int(row["pid"])
            groups.add(group)
            return manager, run_id, events, task, group

        def started(events, node):
            return any(event["type"] == "node_started" and event.get("nodeId") == node for event in events)

        async def record(name, result, group, detail):
            captured = {int(row["pid"]) for row in tree_rows(group)} | {group}
            # Callers capture the complete tree while it is still alive.
            captured.update(detail.pop("captured", set()))
            cleanup = await gone(group, captured, str(copied))
            report["checks"].append({"name": name, "status": "passed", "result": result,
                                     **detail, "cleanup": cleanup})
            groups.intersection_update({int(row["pgid"]) for row in process_table()})
            print("PASS " + name, flush=True)

        try:
            # The opener stays alive: close only the followed popup via its explicit close button.
            manager, run_id, events, task, group = await begin([
                ("open_page", {"url": fixture.url}),
                ("click_element", {"selector": "#popup", "followNewTab": True}),
                ("click_element", {"selector": "#close"}),
                ("wait_element", {"selector": "#ready"}),
            ])
            await until(lambda: started(events, "n1"), "popup node")
            captured = {int(row["pid"]) for row in tree_rows(group)}
            result = await asyncio.wait_for(task, 15)
            assert result["state"] == "failed", result
            assert result["error"]["code"] == "workflow_page_closed", result
            assert not any(e["type"] == "node_succeeded" and e.get("nodeId") == "n3" for e in events)
            await record("closed_current_page_does_not_switch_to_surviving_opener", result, group,
                         {"captured": captured, "method": "real popup close button invokes window.close(); native OS red-close button not exercised"})

            # Pause the real main Chromium process before the context-ready handshake.
            manager, run_id, events, task, group = await begin([("wait_element", {"selector": "#never"})])
            browser = await until(
                lambda: next((row for row in tree_rows(group) if row["command"].startswith(str(executable))
                              and "--type=" not in row["command"]), None), "Chromium process during launch",
            )
            os.kill(int(browser["pid"]), signal.SIGSTOP)
            assert not any(e["type"] == "ready" for e in events), "Context became ready before startup stop was controlled"
            captured = {int(row["pid"]) for row in tree_rows(group)}
            await asyncio.wait_for(manager.stop(run_id), 12)
            result = await task
            assert result["state"] == "cancelled", result
            await record("stop_during_real_browser_startup", result, group,
                         {"captured": captured, "method": "SIGSTOP owned Chromium before ready; manager stop must force-reap the paused process"})

            fixture.requests.clear()
            manager, run_id, events, task, group = await begin([("open_page", {"url": fixture.url + "/hang"})])
            await until(lambda: "/hang" in fixture.requests, "real navigation awaiting server response")
            captured = {int(row["pid"]) for row in tree_rows(group)}
            assert started(events, "n0")
            await asyncio.wait_for(manager.stop(run_id), 12)
            result = await task
            assert result["state"] == "cancelled", result
            await record("stop_during_pending_navigation", result, group,
                         {"captured": captured, "method": "local HTTP connection accepted; no response sent"})

            fixture.requests.clear()
            manager, run_id, events, task, group = await begin([
                ("open_page", {"url": fixture.url + "/font-page", "waitUntil": "domcontentloaded"}),
                ("screenshot", {"screenshotType": "viewport"}),
            ])
            await until(lambda: started(events, "n1") and "/font-hang" in fixture.requests,
                        "real screenshot awaiting document.fonts.ready")
            await asyncio.sleep(0.15)
            assert not task.done(), "Screenshot did not remain pending on the controlled font"
            captured = {int(row["pid"]) for row in tree_rows(group)}
            await asyncio.wait_for(manager.stop(run_id), 12)
            result = await task
            assert result["state"] == "cancelled", result
            assert not any("artifact" in e for e in events)
            assert not list((workspace / "runs" / run_id).rglob("*.png"))
            await record("stop_during_real_screenshot", result, group,
                         {"captured": captured, "method": "screenshot pending on actual font resource; no image output after stop"})

            manager, run_id, events, task, group = await begin([
                ("open_page", {"url": fixture.url}), ("wait_element", {"selector": "#never"}),
            ])
            await until(lambda: started(events, "n1"), "worker ready for abrupt termination")
            captured = {int(row["pid"]) for row in tree_rows(group)}
            os.kill(group, signal.SIGKILL)
            result = await asyncio.wait_for(task, 12)
            assert result["state"] == "failed", result
            await record("abrupt_worker_exit_reaps_real_browser_tree", result, group,
                         {"captured": captured, "method": "SIGKILL source worker only; manager performs remaining tree cleanup"})

            # Exercise the real service parent, not a fixture process standing in for it.
            token, host_token = uuid4().hex, uuid4().hex
            sidecar = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "autoflow", "--data-dir", str(workspace),
                "--instance-id", str(uuid4()), "--port", "0",
                cwd=ROOT, env={**env, "AUTOFLOW_INSTANCE_TOKEN": token, "AUTOFLOW_HOST_TOKEN": host_token},
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            assert sidecar.stdout is not None
            line = await asyncio.wait_for(sidecar.stdout.readline(), 20)
            assert line.startswith(b"AUTOFLOW_READY "), line
            base = "http://127.0.0.1:" + str(json.loads(line.removeprefix(b"AUTOFLOW_READY "))["port"])
            profile_read = await asyncio.to_thread(http_json, base, token, "profiles", {
                "name": "Crash cleanup smoke", "browserVersion": version, "headless": True, "proxyMode": "none",
            })
            document, layout = workflow([("open_page", {"url": fixture.url}), ("wait_element", {"selector": "#never"})])
            run_id = str(uuid4())
            await asyncio.to_thread(http_json, base, token, "workflows/runs", {
                "runId": run_id, "profileId": profile_read["id"], "document": document, "layout": layout,
            })
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                run = await asyncio.to_thread(http_json, base, token, "workflows/runs/" + run_id)
                if run["state"] == "running" and run["currentNodeId"] == "n1":
                    break
                await asyncio.sleep(0.03)
            else:
                raise AssertionError("Sidecar run never reached real browser wait")
            row = await until(lambda: next((row for row in process_table()
                                           if int(row["ppid"]) == sidecar.pid and "--workflow-worker" in row["command"]), None),
                              "sidecar-owned workflow worker")
            group = int(row["pid"])
            groups.add(group)
            rows = tree_rows(group)
            captured = {int(row["pid"]) for row in rows}
            browser = next(row for row in rows if row["command"].startswith(str(executable)) and "--type=" not in row["command"])
            os.kill(int(browser["pid"]), signal.SIGSTOP)
            sidecar.kill()
            await sidecar.wait()
            await record("abrupt_sidecar_exit_reaps_unresponsive_real_browser_tree", {"sidecarExit": sidecar.returncode}, group,
                         {"captured": captured, "method": "SIGSTOP owned Chromium then SIGKILL real HTTP sidecar; child parent watcher must reap all descendants"})
            visits = list(fixture.requests)
            sidecar = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "autoflow", "--data-dir", str(workspace),
                "--instance-id", str(uuid4()), "--port", "0", cwd=ROOT,
                env={**env, "AUTOFLOW_INSTANCE_TOKEN": token, "AUTOFLOW_HOST_TOKEN": host_token},
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            assert sidecar.stdout is not None
            line = await asyncio.wait_for(sidecar.stdout.readline(), 20)
            assert line.startswith(b"AUTOFLOW_READY "), line
            base = "http://127.0.0.1:" + str(json.loads(line.removeprefix(b"AUTOFLOW_READY "))["port"])
            recovered = await asyncio.to_thread(http_json, base, token, "workflows/runs/" + run_id)
            assert recovered["state"] == "interrupted", recovered["state"]
            await asyncio.sleep(0.3)
            assert fixture.requests == visits, "Restart replayed browser actions"
            assert not any(row["command"].startswith(str(copied)) or
                           (int(row["ppid"]) == sidecar.pid and "--workflow-worker" in row["command"])
                           for row in process_table()), "Restart spawned a browser or workflow worker"

            def graceful_shutdown():
                request = Request(base + "/internal/lifecycle/shutdown", data=b"{}",
                                  headers={"x-autoflow-host-token": host_token, "Content-Type": "application/json"})
                with build_opener(ProxyHandler({})).open(request, timeout=10) as response:
                    return json.load(response)

            assert (await asyncio.to_thread(graceful_shutdown))["stopping"]
            await asyncio.wait_for(sidecar.wait(), 12)
            assert sidecar.returncode == 0
            report["checks"].append({
                "name": "crashed_sidecar_restart_marks_interrupted_without_replay",
                "status": "passed", "recoveredState": recovered["state"],
                "newBrowserProcesses": 0, "newPageRequests": 0, "gracefulShutdownExit": 0,
            })
            print("PASS crashed_sidecar_restart_marks_interrupted_without_replay", flush=True)
            report["complete"] = True
        finally:
            fixture.close()
            if sidecar is not None and sidecar.returncode is None:
                sidecar.kill()
                await sidecar.wait()
            for group in list(groups):
                try:
                    if group_rows(group):
                        os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for manager in managers:
                await manager.shutdown()
            for group in list(groups):
                await gone(group, {group}, str(copied))
    report["temporaryWorkspaceRemoved"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-directory", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/migration/automation-studio-m2-qa/worker.json")
    args = parser.parse_args()
    report = {"timestamp": datetime.now(UTC).isoformat(), "platform": sys.platform,
              "arch": platform.machine(), "mode": "source", "checks": [], "complete": False,
              "limitations": ["Windows not executed", "Native window close button not exercised; a real popup close button covers the same closed-page ownership guard"]}
    try:
        asyncio.run(smoke(args, report))
    except BaseException as error:
        report["complete"] = False
        report["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
