"""Use the shared structured scheduler; Android input stays with the owning sidecar."""
import asyncio
import json
import sys
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from autoflow.application.workflows.execution import WorkflowExecution
from autoflow.domain.workflows.models import WorkflowError, WorkflowIssue


def error_of(error: Exception, node_id: str) -> dict[str, Any]:
    if isinstance(error, WorkflowError):
        issue = error.issues[0] if error.issues else None
        return {"code": issue.code if issue else error.code, "message": error.message,
                "nodeId": node_id, "path": issue.path if issue else []}
    return {"code": "ANDROID_TIMEOUT" if isinstance(error, TimeoutError) else "ANDROID_WORKER_FAILED",
            "message": "安卓动作超时" if isinstance(error, TimeoutError) else "安卓执行进程失败", "nodeId": node_id, "path": []}


def main() -> int:
    lock, stopped = Lock(), Event()
    identity: dict[str, Any] = {}

    def send(message: dict[str, Any]) -> None:
        if message.get("type") == "node_started":
            identity.update({key: message[key] for key in ("nodeId", "executionId", "loopPath")})
        with lock:
            sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    def heartbeat() -> None:
        while not stopped.wait(5):
            send({"type": "heartbeat"})

    async def execute(initial: dict[str, Any]) -> dict[str, Any]:
        variables = initial["variables"]

        async def action(node: dict[str, Any], args: dict[str, Any], deadline: float) -> dict[str, Any] | None:
            request_id = str(uuid4())
            send({"type": "android_command", "requestId": request_id, **identity, "operation": node["type"], "args": args})
            line = await asyncio.to_thread(sys.stdin.readline, 65537)
            if not line or len(line.encode()) > 65536:
                raise ValueError("Invalid command response")
            response = json.loads(line)
            if response["requestId"] != request_id:
                raise ValueError("Invalid command response")
            if response.get("error"):
                e = response["error"]
                raise WorkflowError(e["code"], e["message"], 422, [WorkflowIssue(node["id"], e.get("path", []), e["code"], e["message"])])
            if "variableName" in args:
                variables[args["variableName"]] = response["result"]
            return response.get("artifact")

        async def page_condition(_rule: dict[str, Any], _deadline: float) -> bool:
            raise WorkflowError("WORKFLOW_RUNTIME_MISMATCH", "安卓流程不支持网页条件", 422)

        scheduler = WorkflowExecution(variables, send, action, page_condition, error_of)
        plan = initial.get("plan") or [{"nodeId": i} for i in initial["nodeIds"]]
        return await scheduler.run(initial["document"], plan, ready_message="安卓设备已连接")

    try:
        initial = json.loads(sys.stdin.readline(65537))
        Thread(target=heartbeat, daemon=True).start()
        result = asyncio.run(execute(initial))
        send({"type": "finished", **result})
        return 0 if result["state"] == "succeeded" else 1
    except Exception:  # noqa: BLE001 -- no raw pipe errors in public events.
        send({"type": "finished", "state": "failed", "error": error_of(ValueError(), identity.get("nodeId", ""))})
        return 1
    finally:
        stopped.set()
