"""Isolated PM5 management QA sidecar.

Reachable only through the desktop development-only QA switch. Everything the
PM5 acceptance depends on stays real: the full bootstrap, SQLite, the
environment store, the project/automation/run APIs and the CloakBrowser opener
and closer behind "进入当前浏览器" / "结束并保留".

Only the batch executor is removed. PM5 hands a live task's work copy to the
human so they can log in by hand, and the real executor would launch its own
browser on that same profile the moment the human's window is already open,
producing a Chromium singleton hand-off that kills the task's page. That
production-executor integration is explicitly out of this stage's scope, so the
queued run is left queued and the human owns the work copy for the whole chain.
"""

from __future__ import annotations

import argparse
import os
import socket
from pathlib import Path
from threading import Event, Thread

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.parent import watch_parent
from autoflow.bootstrap.ready import ready_line


def create_qa_app(settings: Settings):
    app = create_app(settings)
    scheduler = app.state.project_run_scheduler
    # The dispatch loop is the only thing that would hand this run to the real
    # workflow core, so leaving it unstarted keeps the run queued for the whole
    # manual take-over while every management fact stays real.
    app.router.on_startup[:] = [
        handler
        for handler in app.router.on_startup
        if not (
            getattr(handler, "__self__", None) is scheduler
            and getattr(handler, "__name__", "") == "startup"
        )
    ]
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
            app,
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
        sock.close()


if __name__ == "__main__":
    main()
