"""Isolated PM7 management QA sidecar.

Reachable only through the desktop development-only QA switch
(``AUTOFLOW_QA_SIDECAR_MODULE=tests.qa.pm7_sidecar``). It reuses the PM4
isolated executor so run facts are real, and adds the PM7-only fault injection
consumed by ``scripts/qa-project-management-pm7.mjs``. The production bootstrap
is unchanged: every fault endpoint is ``include_in_schema=False`` and only
exists inside this module.
"""

from __future__ import annotations

import argparse
import os
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select

from autoflow.application.projects import statistics as statistics_module
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.parent import watch_parent
from autoflow.bootstrap.ready import ready_line
from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)
from tests.qa.pm4_fake_executor import CREATE_ACCOUNT, PauseBarrier
from tests.qa.pm4_sidecar import create_qa_app as _create_pm4_qa_app

FAULT_KINDS = (
    "overview-read-failure",
    "statistics-read-failure",
    "statistics-ttl",
    "followup-conflict",
    "response-loss",
    "late-event",
    "executor-fail",
    "executor-pause",
    "executor-resume",
)

# A negative TTL makes every freshly minted result set born expired, so the
# drill endpoint answers 410 without touching production constants at import.
_PRODUCTION_TTL = statistics_module.RESULT_TTL
_EXPIRED_TTL = timedelta(seconds=-1)
_LATE_EVENT_PAYLOAD = {
    "level": "warning",
    "message": "PM7 QA injected late event after the terminal transition",
}


class ResponseDrop:
    """Outermost ASGI layer that can swallow a whole response body.

    The handler has already committed its transaction by the time the response
    starts, so dropping the body is exactly the "unknown result" the caller must
    recover from by querying the original operation identity.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self.rules: list[dict[str, str]] = []

    def arm(self, method: str, path: str, label: str) -> None:
        self.rules.append({"method": method, "path": path, "label": label})

    def take(self, scope: dict[str, Any]) -> dict[str, str] | None:
        if scope["type"] != "http":
            return None
        for index, rule in enumerate(self.rules):
            if rule["method"] == scope["method"] and rule["path"] in scope["path"]:
                return self.rules.pop(index)
        return None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        rule = self.take(scope)
        if rule is None:
            await self.app(scope, receive, send)
            return

        async def guarded(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.body":
                return
            await send(message)

        await self.app(scope, receive, guarded)


def _bump_task_revision(
    factory: Any, project_id: str | None, task_id: str
) -> dict[str, Any]:
    with factory() as session:
        task = session.get(ProjectTaskRow, task_id)
        if task is None or (project_id is not None and task.project_id != project_id):
            raise HTTPException(status_code=404, detail="task not found")
        # The follow-up guard compares the run's status revision, not a task column.
        run = session.get(WorkflowRunRow, task.run_id)
        if run is None:
            raise HTTPException(status_code=409, detail="run facts incomplete")
        run.status_revision += 1
        session.commit()
        return {
            "taskId": task.id,
            "statusRevision": run.status_revision,
            "runId": run.id,
        }


def _append_late_event(factory: Any, task_id: str) -> dict[str, Any]:
    with factory() as session:
        task = session.get(ProjectTaskRow, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        run = session.get(WorkflowRunRow, task.run_id)
        if run is None:
            raise HTTPException(status_code=409, detail="run facts incomplete")
        sequence = run.last_sequence + 1
        session.add(
            WorkflowRunEventRow(
                run_id=run.id,
                sequence=sequence,
                event_id=str(uuid4()),
                execution_generation=run.execution_generation,
                kind="log",
                node_id=None,
                node_visit_id=None,
                attempt=None,
                occurred_at=datetime.now(UTC),
                payload=dict(_LATE_EVENT_PAYLOAD),
            )
        )
        run.last_sequence = sequence
        session.commit()
        return {
            "taskId": task.id,
            "runId": run.id,
            "sequence": sequence,
            "runStatus": run.status,
        }


def _latest_terminal_task(factory: Any, project_id: str) -> str:
    with factory() as session:
        rows = session.scalars(
            select(ProjectTaskRow)
            .where(ProjectTaskRow.project_id == project_id)
            .order_by(ProjectTaskRow.created_at.desc())
        ).all()
        for row in rows:
            run = session.get(WorkflowRunRow, row.run_id)
            if run is not None and run.status in {
                "succeeded",
                "failed",
                "cancelled",
                "timed_out",
                "interrupted",
            }:
                return row.id
    raise HTTPException(status_code=409, detail="项目内还没有终态任务")


def _install_pm7_controls(app: Any) -> None:
    factory = app.state.session_factory
    drop = app.state.pm7_drop
    faults: dict[str, Any] = {"armed": [], "statisticsTtl": "production", "pauseBarrier": None}
    app.state.pm7_faults = faults

    def runner() -> Any:
        return app.state.pm4_qa_runner.runner

    @app.post("/api/v1/qa/pm7/fault", include_in_schema=False)
    async def arm_fault(request: Request) -> dict[str, Any]:
        body = await request.json()
        kind = body.get("kind")
        if kind not in FAULT_KINDS:
            raise HTTPException(status_code=422, detail=f"unknown fault kind: {kind}")
        task_id = body.get("taskId")
        project_id = body.get("projectId")
        result: dict[str, Any] = {"injected": True, "kind": kind}
        if kind == "overview-read-failure":
            # The renderer retries reads twice, so a single dropped body would be
            # masked by the retry. Arm the whole attempt budget instead.
            for _ in range(3):
                drop.arm("GET", "/overview", kind)
        elif kind == "response-loss":
            # "Committed but the caller never learned the outcome": the POST body is
            # dropped and so is the by-key lookup the renderer runs right after, so
            # the user really sees the unknown-result state and must reconcile.
            drop.arm("POST", "/follow-up-batches", kind)
            drop.arm("GET", "/operations/by-idempotency-key/", kind)
        elif kind == "statistics-read-failure":
            # 与 overview-read-failure 同理：渲染层读重试两次，必须覆盖整段尝试预算。
            for _ in range(3):
                drop.arm("GET", "/statistics", kind)
            faults["statisticsRead"] = "failed"
        elif kind == "statistics-ttl":
            statistics_module.RESULT_TTL = _EXPIRED_TTL
            faults["statisticsTtl"] = "expired"
        elif kind == "followup-conflict":
            target = task_id or (
                _latest_terminal_task(factory, project_id) if project_id else None
            )
            if target is None:
                raise HTTPException(status_code=422, detail="taskId 或 projectId 必填")
            result.update(_bump_task_revision(factory, project_id, target))
        elif kind == "late-event":
            target = task_id or (
                _latest_terminal_task(factory, project_id) if project_id else None
            )
            if target is None:
                raise HTTPException(status_code=422, detail="taskId 或 projectId 必填")
            result.update(_append_late_event(factory, target))
        elif kind == "executor-fail":
            step = body.get("step", CREATE_ACCOUNT)
            runner()._fail_step = None if step is None else step
            result["failStep"] = step
        elif kind == "executor-pause":
            step = body.get("step", CREATE_ACCOUNT)
            barrier = PauseBarrier(before_step=step)
            runner()._pause_barrier = barrier
            faults["pauseBarrier"] = barrier
            result["beforeStep"] = step
        elif kind == "executor-resume":
            barrier = runner()._pause_barrier
            runner()._pause_barrier = None
            faults["pauseBarrier"] = None
            if barrier is not None:
                barrier.release()
            result["released"] = barrier is not None
        faults["armed"].append(result)
        return result

    @app.get("/api/v1/qa/pm7/state", include_in_schema=False)
    async def fault_state() -> dict[str, Any]:
        return {
            "armed": list(faults["armed"]),
            "pendingResponseDrops": list(drop.rules),
            "statisticsTtl": faults["statisticsTtl"],
            "executorFailStep": runner()._fail_step,
            "executorPaused": runner()._pause_barrier is not None,
        }

    @app.post("/api/v1/qa/pm7/clear", include_in_schema=False)
    async def clear_faults() -> dict[str, bool]:
        drop.rules.clear()
        statistics_module.RESULT_TTL = _PRODUCTION_TTL
        runner()._fail_step = None
        if runner()._pause_barrier is not None:
            runner()._pause_barrier.release()
        runner()._pause_barrier = None
        faults["pauseBarrier"] = None
        faults["armed"].clear()
        faults["statisticsTtl"] = "production"
        return {"cleared": True}


def create_qa_app(settings: Settings, *, mode: str = "f"):
    if mode != "f":
        raise ValueError(f"PM7 QA requires the PM4-F executor mode, got {mode}")
    app = _create_pm4_qa_app(settings, mode="f")
    app.state.pm7_drop = ResponseDrop(app)
    _install_pm7_controls(app)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        parser.error("sidecar host must be 127.0.0.1")
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    if args.parent_pid is not None and args.parent_pid <= 0:
        parser.error("parent PID must be positive")
    if not Path(args.data_dir).is_absolute():
        parser.error("data directory must be absolute")

    import uvicorn

    settings = Settings(
        data_dir=args.data_dir,
        instance_id=args.instance_id,
        instance_token=os.environ.get("AUTOFLOW_INSTANCE_TOKEN"),
        parent_pid=args.parent_pid,
        renderer_origin=os.environ.get("AUTOFLOW_RENDERER_ORIGIN"),
        host_token=os.environ.get("AUTOFLOW_HOST_TOKEN"),
    )
    app = create_qa_app(settings)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(socket.SOMAXCONN)
    actual_port = sock.getsockname()[1]
    print(
        ready_line(
            port=actual_port,
            api_version=settings.api_version,
            instance_id=settings.instance_id,
        ),
        flush=True,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app.state.pm7_drop,
            host=args.host,
            port=actual_port,
            log_level="warning",
            timeout_graceful_shutdown=1,
        )
    )

    @app.post("/internal/lifecycle/shutdown", include_in_schema=False)
    async def request_shutdown() -> dict[str, bool]:
        server.should_exit = True
        return {"stopping": True}

    stopped = Event()
    if args.parent_pid:

        def parent_exited() -> None:
            server.should_exit = True

        Thread(
            target=watch_parent,
            args=(args.parent_pid, stopped, parent_exited),
            daemon=True,
        ).start()
    try:
        server.run(sockets=[sock])
    finally:
        stopped.set()


if __name__ == "__main__":
    main()
