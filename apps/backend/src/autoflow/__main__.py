import argparse
import os
import socket

import uvicorn

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.ready import ready_line


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(socket.SOMAXCONN)
    actual_port = sock.getsockname()[1]
    settings = Settings(
        data_dir=os.environ.get("AUTOFLOW_DATA_DIR", "/tmp/autoflow"),
        instance_id=args.instance_id,
        instance_token=os.environ.get("AUTOFLOW_INSTANCE_TOKEN"),
        parent_pid=args.parent_pid,
    )
    print(ready_line(port=actual_port, api_version=settings.api_version, instance_id=settings.instance_id), flush=True)
    config = uvicorn.Config(create_app(settings), host=args.host, port=actual_port, log_level="warning")
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
