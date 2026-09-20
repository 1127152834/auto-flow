"""Isolated PM8 lifecycle QA sidecar.

Reachable only through the desktop development-only QA switch
(``AUTOFLOW_QA_SIDECAR_MODULE=tests.qa.pm8_sidecar``). It reuses the PM7 app,
which already carries the PM4 isolated executor and the response-drop layer, and
adds only the lifecycle faults ``scripts/qa-project-management-pm8.mjs`` needs.

The production bootstrap is untouched: every route here is
``include_in_schema=False`` and exists only inside this module.
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
from sqlalchemy import update

from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.parent import watch_parent
from autoflow.bootstrap.ready import ready_line
from autoflow.domain.environments.models import EnvironmentInstance
from autoflow.infrastructure.database.project_data_models import DataImpactRow
from tests.qa.pm7_sidecar import create_qa_app as _create_pm7_qa_app

FAULT_KINDS = (
    "expire-lifecycle-impact",
    "lifecycle-response-loss",
    "leak-work-copy",
)

# One second short of a live confirmation, so the command under test answers 412
# without touching any production constant.
_EXPIRED_AT = timedelta(seconds=-1)


def _expire_impacts(factory: Any, project_id: str | None) -> dict[str, Any]:
    """Backdate stored impact confirmations; the commands must re-check them."""
    with factory() as session:
        statement = update(DataImpactRow).values(
            expires_at=datetime.now(UTC) + _EXPIRED_AT
        )
        if project_id is not None:
            statement = statement.where(DataImpactRow.project_id == project_id)
        result = session.execute(statement)
        session.commit()
        return {"expiredImpacts": result.rowcount}


def _leak_work_copy(app: Any, body: dict[str, Any]) -> dict[str, Any]:
    """Leave behind a real isolated work copy, as an interrupted cleanup would.

    ``quiesce_instance`` marks an instance ``closed`` before ``close_instance``
    removes its directory, so a process killed in between leaves exactly this
    durable state: browser gone, work copy still on disk, instance not busy. The
    QA sidecar cannot kill itself mid-cleanup, so it recreates that state through
    the real environment repository and store instead of writing rows by hand;
    every later step (delete, residue reporting, retry, purge) stays production
    code.
    """
    project_id = body.get("projectId")
    profile_id = body.get("profileId")
    if not project_id or not profile_id:
        raise HTTPException(
            status_code=422, detail="leak-work-copy requires projectId and profileId"
        )
    service = app.state.environment_service
    instance_id = str(uuid4())
    directory = service.store.prepare_instance(instance_id)
    (directory / "crash-note.txt").write_text(
        "interrupted before the work copy was removed", encoding="utf-8"
    )
    now = datetime.now(UTC)
    record = EnvironmentInstance(
        instance_id=instance_id,
        project_id=project_id,
        environment_id=None,
        state="closed",
        source="newFromProfile",
        source_content_generation=None,
        instance_use_generation=1,
        active_task_id=None,
        active_run_id=None,
        maintenance_operation_id=None,
        profile_id=profile_id,
        created_at=now,
        updated_at=now,
    )
    with app.state.session_factory() as session:
        service.environments.reserve_instance_in_session(session, record, None)
        session.commit()
    return {
        "instanceId": instance_id,
        "directory": str(directory),
        "state": "closed",
    }


def _install_pm8_controls(app: Any) -> None:
    factory = app.state.session_factory
    drop = app.state.pm7_drop
    faults: dict[str, Any] = {"armed": []}
    app.state.pm8_faults = faults

    @app.post("/api/v1/qa/pm8/fault", include_in_schema=False)
    async def arm_fault(request: Request) -> dict[str, Any]:
        body = await request.json()
        kind = body.get("kind")
        if kind not in FAULT_KINDS:
            raise HTTPException(status_code=422, detail=f"unknown fault kind: {kind}")
        project_id = body.get("projectId")
        result: dict[str, Any] = {"injected": True, "kind": kind}
        if kind == "expire-lifecycle-impact":
            result.update(_expire_impacts(factory, project_id))
        elif kind == "leak-work-copy":
            result.update(_leak_work_copy(app, body))
        elif kind == "lifecycle-response-loss":
            # "Committed but the caller never learned the outcome": the command
            # body is dropped together with the by-key lookup the renderer runs
            # right after, so the user must reconcile the original identity.
            drop.arm("POST", "/archive", kind)
            drop.arm("POST", "/restore", kind)
            drop.arm("GET", "/operations/by-idempotency-key/", kind)
        faults["armed"].append(result)
        return result

    @app.get("/api/v1/qa/pm8/state", include_in_schema=False)
    async def fault_state() -> dict[str, Any]:
        return {
            "armed": list(faults["armed"]),
            "pendingResponseDrops": list(drop.rules),
        }

    @app.post("/api/v1/qa/pm8/clear", include_in_schema=False)
    async def clear_faults() -> dict[str, bool]:
        drop.rules.clear()
        faults["armed"].clear()
        return {"cleared": True}


def create_qa_app(settings: Settings, *, mode: str = "f"):
    if mode != "f":
        raise ValueError(f"PM8 QA requires the PM4-F executor mode, got {mode}")
    app = _create_pm7_qa_app(settings, mode="f")
    _install_pm8_controls(app)
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
