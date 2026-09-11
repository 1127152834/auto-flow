import argparse
import os
import socket
from pathlib import Path
from threading import Event, Thread

import uvicorn

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.parent import watch_parent
from autoflow.bootstrap.ready import ready_line


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    if args.parent_pid is not None and args.parent_pid <= 0:
        parser.error("parent PID must be positive")
    if args.host != "127.0.0.1":
        parser.error("sidecar host must be 127.0.0.1")
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    if not Path(args.data_dir).is_absolute():
        parser.error("data directory must be absolute")

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
    config = uvicorn.Config(app, host=args.host, port=actual_port, log_level="warning")
    server = uvicorn.Server(config)
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
