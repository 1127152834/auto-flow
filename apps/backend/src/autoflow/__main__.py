import argparse
import os
import runpy
import socket
import sys
from pathlib import Path
from threading import Event, Thread

from autoflow.bootstrap.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-script", nargs=argparse.REMAINDER)
    parser.add_argument("--kernel-worker", action="store_true")
    parser.add_argument("--test-browser-worker", action="store_true")
    parser.add_argument("--workflow-worker", action="store_true")
    parser.add_argument("--inspection-worker", action="store_true")
    parser.add_argument("--project-workflow-worker", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--instance-id")
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    if args.python_script is not None:
        if not args.python_script:
            parser.error("--python-script requires a script path")
        original_argv, original_path = sys.argv, list(sys.path)
        try:
            sys.argv = args.python_script
            sys.path.insert(0, str(Path(sys.argv[0]).resolve().parent))
            runpy.run_path(sys.argv[0], run_name="__main__")
        finally:
            sys.argv = original_argv
            sys.path[:] = original_path
        return
    if args.kernel_worker:
        from autoflow.bootstrap.kernel_worker import kernel_worker_main

        raise SystemExit(kernel_worker_main())
    if args.test_browser_worker:
        from autoflow.bootstrap.test_browser_worker import test_browser_worker_main

        raise SystemExit(test_browser_worker_main())
    if args.project_workflow_worker:
        from autoflow.bootstrap.workflow_worker import project_workflow_worker_main

        raise SystemExit(project_workflow_worker_main())
    if args.workflow_worker:
        from autoflow.bootstrap.workflow_worker import workflow_worker_main

        raise SystemExit(workflow_worker_main())
    if args.inspection_worker:
        from autoflow.bootstrap.inspection_worker import inspection_worker_main

        raise SystemExit(inspection_worker_main())
    if args.instance_id is None:
        parser.error("the following arguments are required: --instance-id")
    if args.data_dir is None:
        parser.error("the following arguments are required: --data-dir")
    if args.parent_pid is not None and args.parent_pid <= 0:
        parser.error("parent PID must be positive")
    if args.host != "127.0.0.1":
        parser.error("sidecar host must be 127.0.0.1")
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    if not Path(args.data_dir).is_absolute():
        parser.error("data directory must be absolute")

    import uvicorn

    from autoflow.bootstrap.config import Settings
    from autoflow.bootstrap.parent import watch_parent
    from autoflow.bootstrap.ready import ready_line

    settings = Settings(
        data_dir=args.data_dir,
        instance_id=args.instance_id,
        instance_token=os.environ.get("AUTOFLOW_INSTANCE_TOKEN"),
        parent_pid=args.parent_pid,
        renderer_origin=os.environ.get("AUTOFLOW_RENDERER_ORIGIN"),
        host_token=os.environ.get("AUTOFLOW_HOST_TOKEN"),
    )
    app = create_app(settings)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(socket.SOMAXCONN)
    actual_port = sock.getsockname()[1]
    print(ready_line(port=actual_port, api_version=settings.api_version, instance_id=settings.instance_id), flush=True)
    # Bound connection draining (including SSE) before application/worker cleanup.
    # The desktop supervisor reserves a further 6s for worker shutdown plus margin.
    config = uvicorn.Config(
        app, host=args.host, port=actual_port, log_level="warning",
        timeout_graceful_shutdown=1,
    )
    server = uvicorn.Server(config)

    @app.post("/internal/lifecycle/shutdown", include_in_schema=False)
    async def request_shutdown() -> dict[str, bool]:
        # Uses create_app's host-only authentication, including Origin rejection.
        # HTTP cooperates on Windows too, where SIGTERM forcibly ends the process.
        server.should_exit = True
        return {"stopping": True}

    stopped = Event()
    if args.parent_pid:
        def parent_exited() -> None:
            server.should_exit = True

        Thread(target=watch_parent, args=(args.parent_pid, stopped, parent_exited), daemon=True).start()
    try:
        server.run(sockets=[sock])
    finally:
        stopped.set()
        sock.close()


if __name__ == "__main__":
    main()
