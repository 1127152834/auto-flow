"""JSONL node runner. All Android input is delegated to the owning sidecar."""
import json
import sys
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.run_validation import resolve_node_config


def main() -> int:
    lock, stopped = Lock(), Event()

    def send(message: dict[str, Any]) -> None:
        with lock:
            sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    def heartbeat() -> None:
        while not stopped.wait(5):
            send({"type": "heartbeat"})

    try:
        initial = json.loads(sys.stdin.readline(65537))
        variables = initial["variables"]
        nodes = {node["id"]: node for node in initial["document"]["nodes"]}
        Thread(target=heartbeat, daemon=True).start()
        send({"type": "ready"})
        for node_id in initial["nodeIds"]:
            node = nodes[node_id]
            args = resolve_node_config(node, variables)
            request_id = str(uuid4())
            send({"type": "node_started", "nodeId": node_id})
            send({"type": "android_command", "requestId": request_id, "nodeId": node_id, "operation": node["type"], "args": args})
            line = sys.stdin.readline(65537)
            if not line:
                return 1
            response = json.loads(line)
            if response["requestId"] != request_id:
                raise ValueError("Invalid command response")
            if response.get("error"):
                send({"type": "node_failed", "nodeId": node_id, "error": response["error"]})
                send({"type": "finished", "state": "failed", "error": response["error"]})
                return 1
            if "variableName" in args:
                variables[args["variableName"]] = response["result"]
            send({"type": "node_succeeded", "nodeId": node_id})
        send({"type": "finished", "state": "succeeded", "error": None})
        return 0
    except Exception:  # noqa: BLE001 -- control pipe exposes only safe structured failures.
        send({"type": "finished", "state": "failed", "error": {"code": "ANDROID_WORKER_FAILED", "message": "安卓节点执行进程失败", "nodeId": None, "path": []}})
        return 1
    finally:
        stopped.set()
