"""Exercise the real Android runtime through the formal HTTP contract.

Requires an explicitly prepared workspace. Keeps its devices and run artifacts.
"""
import argparse
from copy import deepcopy
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx


def sample() -> dict:
    definitions = [
        ("android_launch_app", {"packageName": "com.android.settings", "timeoutSeconds": 30}),
        ("android_screenshot", {"variableName": "before", "timeoutSeconds": 15}),
        ("android_manual", {"prompt": "在原生窗口进入一个设置子页，回到这里完成并继续。", "timeoutSeconds": 600}),
        ("android_key", {"key": "BACK", "timeoutSeconds": 15}),
        ("android_screenshot", {"variableName": "after", "timeoutSeconds": 15}),
    ]
    nodes = [{"id": f"android-{i}", "type": kind, "label": label, "config": config} for i, ((kind, config), label) in enumerate(zip(definitions, ["打开设置", "操作前截图", "人工处理", "自动返回", "操作后截图"], strict=True))]
    return {"document": {"id": "7c5f248d-7785-4d90-891f-53d21dfd36e0", "name": "安卓人工接管示例", "schemaVersion": 1, "nodes": nodes, "edges": [{"id": f"edge-{i}", "source": nodes[i]["id"], "target": nodes[i + 1]["id"], "sourceHandle": "out", "targetHandle": "in"} for i in range(len(nodes) - 1)], "variables": []},
            "layout": {"nodes": {node["id"]: {"x": 120 + i * 240, "y": 160} for i, node in enumerate(nodes)}, "viewport": {"x": 0, "y": 0, "zoom": .8}}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    token = str(uuid4())
    command = [str(args.executable)] if args.executable else [sys.executable, "-m", "autoflow"]
    def launch():
        process = subprocess.Popen([*command, "--instance-id", "android-smoke", "--data-dir", str(args.data_dir.resolve()), "--port", "0"], stdout=subprocess.PIPE, env={**os.environ, "AUTOFLOW_INSTANCE_TOKEN": token})
        try:
            assert process.stdout is not None
            import selectors
            with selectors.DefaultSelector() as ready:
                ready.register(process.stdout, selectors.EVENT_READ)
                assert ready.select(40), "sidecar did not become ready"
            line = process.stdout.readline().decode()
            assert line.startswith("AUTOFLOW_READY "), line
            port = json.loads(line.removeprefix("AUTOFLOW_READY "))["port"]
            return process, httpx.Client(base_url=f"http://127.0.0.1:{port}/api/v1", headers={"x-autoflow-token": token}, timeout=220, trust_env=False)
        except BaseException:
            process.kill()
            process.wait(timeout=5)
            raise
    process, client = launch()
    run_id = None
    try:

        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.is_success, (response.status_code, response.text)
            return response.json()

        def until(predicate, seconds=210):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                value = request("GET", f"/workflows/runs/{run_id}")
                if predicate(value):
                    return value
                assert value["state"] not in {"failed", "interrupted"}, value
                time.sleep(.2)
            raise AssertionError("run did not reach expected state")

        device = request("GET", "/android/devices")[0]
        assert device["control"] == "idle", device
        content = sample()
        run_id = str(uuid4())
        payload = {"runId": run_id, **content, "target": {"kind": "android", "deviceId": device["deviceId"]}}
        request("POST", "/workflows/runs", json=payload)
        waiting = until(lambda r: r["state"] == "waiting_manual")
        assert len(waiting["artifacts"]) == 1
        handoff_id = waiting["handoff"]["handoffId"]
        request_id = str(uuid4())
        path = f"/workflows/runs/{run_id}/handoffs/{handoff_id}"
        request("POST", path + "/open", json={"requestId": request_id})
        opened = until(lambda r: r["handoff"]["state"] == "open", 35)
        request("POST", path + "/open", json={"requestId": request_id})
        assert request("GET", "/android/devices")[0]["ownerRunId"] == run_id
        print("PASS: real Android launch, screenshot, manual wait, native window and duplicate open", flush=True)
        resume_id = str(uuid4())
        request("POST", path + "/continue", json={"requestId": resume_id})
        request("POST", path + "/continue", json={"requestId": resume_id})
        final = until(lambda r: r["state"] == "succeeded", 40)
        assert len(final["completedNodeIds"]) == 5 and len(final["artifacts"]) == 2
        devices = request("GET", "/android/devices")
        assert devices[0]["control"] == "idle" and devices[0]["ownerRunId"] is None
        events = request("GET", f"/workflows/runs/{run_id}/events")
        assert sum(e["type"] == "resumed" for e in events["items"]) == 1
        args.evidence.mkdir(parents=True, exist_ok=True)
        for i, artifact in enumerate(final["artifacts"]):
            image = client.get(f"/workflows/runs/{run_id}/artifacts/{artifact['id']}")
            assert image.is_success and image.content.startswith(b"\x89PNG\r\n\x1a\n")
            (args.evidence / f"screenshot-{i}.png").write_bytes(image.content)
        (args.evidence / "result.json").write_text(json.dumps({"waiting": waiting, "opened": opened, "final": final, "devices": devices, "events": events}, ensure_ascii=False, indent=2))
        # Save the tested document so the real Studio can open it for user verification.
        existing = client.get("/workflows/" + content["document"]["id"])
        if existing.status_code == 404:
            request("POST", "/workflows", json=content)
        (args.evidence / "example.json").write_text(json.dumps(content, ensure_ascii=False, indent=2))
        print("PASS: continue once, automatic BACK, second screenshot, cleanup and ownership release", flush=True)
        faults = []
        def start_case(definitions):
            nonlocal run_id
            content = deepcopy(sample())
            nodes = [{"id": f"case-{i}", "type": kind, "label": kind, "config": config} for i, (kind, config) in enumerate(definitions)]
            content["document"].update(id=str(uuid4()), name="安卓故障验收", nodes=nodes, edges=[{"id": f"e-{i}", "source": nodes[i]["id"], "target": nodes[i+1]["id"], "sourceHandle": "out", "targetHandle": "in"} for i in range(len(nodes)-1)])
            content["layout"]["nodes"] = {n["id"]: {"x": i*240, "y": 100} for i, n in enumerate(nodes)}
            run_id = str(uuid4())
            request("POST", "/workflows/runs", json={"runId": run_id, **content, "target": payload["target"]})

        start_case([("android_launch_app", {"packageName": "local.autoflow.missing.test", "timeoutSeconds": 15})])
        missing = until(lambda r: r["state"] == "failed")
        assert missing["error"]["code"] == "ANDROID_APP_UNAVAILABLE", missing
        faults.append({"case": "missing application", "run": missing})
        start_case([("android_tap", {"x": 20, "y": 20, "basisWidth": 1280, "basisHeight": 720, "timeoutSeconds": 15})])
        mismatch = until(lambda r: r["state"] == "failed")
        assert mismatch["error"]["code"] == "ANDROID_SCREEN_CHANGED", mismatch
        faults.append({"case": "rotated coordinate basis", "run": mismatch})
        start_case([("android_launch_app", {"packageName": "com.android.settings", "timeoutSeconds": 30}), ("android_tap", {"x": 200, "y": 640, "basisWidth": 720, "basisHeight": 1280, "timeoutSeconds": 15}), ("android_screenshot", {"variableName": "tapResult", "timeoutSeconds": 15})])
        tapped = until(lambda r: r["state"] == "succeeded")
        artifact = tapped["artifacts"][0]
        (args.evidence / "tap.png").write_bytes(client.get(f"/workflows/runs/{run_id}/artifacts/{artifact['id']}").content)
        faults.append({"case": "valid coordinate input", "run": tapped})
        start_case([("android_manual", {"prompt": "stop test", "timeoutSeconds": 30})])
        until(lambda r: r["state"] == "waiting_manual")
        stopped = request("POST", f"/workflows/runs/{run_id}/stop")
        assert stopped["state"] == "cancelled"
        faults.append({"case": "stop manual wait", "run": stopped})
        start_case([("android_manual", {"prompt": "timeout test", "timeoutSeconds": 30})])
        expired = until(lambda r: r["state"] == "failed", 45)
        assert expired["error"]["code"] == "ANDROID_MANUAL_TIMEOUT", expired
        faults.append({"case": "real manual deadline", "run": expired})
        start_case([("android_manual", {"prompt": "restart test", "timeoutSeconds": 30})])
        restarting = until(lambda r: r["state"] == "waiting_manual")
        restart_path = f"/workflows/runs/{run_id}/handoffs/{restarting['handoff']['handoffId']}"
        request("POST", restart_path + "/open", json={"requestId": str(uuid4())})
        until(lambda r: r["handoff"]["state"] == "open", 35)
        process.kill()  # Only the sidecar created by this smoke; native identities must recover.
        process.wait(timeout=5)
        client.close()
        process, client = launch()
        recovered = request("GET", f"/workflows/runs/{run_id}")
        assert recovered["state"] == "interrupted", recovered
        faults.append({"case": "sidecar killed with native window open; recovered without replay", "run": recovered})
        devices = request("GET", "/android/devices")
        assert devices[0]["control"] == "idle" and devices[0]["androidStatus"] == "ready"
        (args.evidence / "faults.json").write_text(json.dumps({"cases": faults, "devices": devices}, ensure_ascii=False, indent=2))
        print("PASS: missing app, stale coordinates, real tap, stop, 30-second manual timeout and crash recovery; Android/data retained", flush=True)

    finally:
        if client is not None and run_id is not None:
            try:
                client.post(f"/workflows/runs/{run_id}/stop")
            finally:
                client.close()
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
