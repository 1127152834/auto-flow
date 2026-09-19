"""Isolated PM6 management QA sidecar.

Reachable only through the desktop development-only QA switch
(``AUTOFLOW_QA_SIDECAR_MODULE``). Everything the PM6 acceptance depends on stays
real: the full bootstrap, SQLite, the FastAPI surface, operation envelopes,
idempotency replay, transactions and the renderer.

Two things are stand-ins, and both are named in the QA report:

* the Google Sheets REST surface (``tests.fixtures.sheets.FakeSheetsTransport``),
  because the acceptance machine has no authorized Google account;
* the operating-system credential store, so an automated run never writes a
  Google secret into the developer's keychain.

The stand-ins sit exactly at the two ports the production code already declares
(``SheetsTransport`` and ``CredentialStore``); no business rule is replaced.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from threading import Event, Thread
from typing import Any

from fastapi import HTTPException, Request
from fastapi.routing import APIRouter

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.parent import watch_parent
from autoflow.bootstrap.ready import ready_line
from autoflow.providers.data.google_sheets import SheetsApiError
from tests.fixtures.sheets import FakeSheetsTransport, FakeTokenTransport

SPREADSHEET_ID = "pm6-source-1"
SPREADSHEET_TITLE = "PM6 来源表"
SHEET_NAME = "记录"
ID_COLUMN = "编号"
MAIL_COLUMN = "邮箱"
CHECK_COLUMN = "校验"
IDENTITY_KEY = "001"
MAIL_VALUE = "remote@example.com"
CHECK_FORMULA = '=LOWER("A@B.COM")'
CHECK_VALUE = "a@b.com"


def seed_grid() -> dict[str, list[list[Any]]]:
    """The recorded remote table the QA chain binds to."""
    return {
        SHEET_NAME: [
            [ID_COLUMN, MAIL_COLUMN, CHECK_COLUMN],
            [IDENTITY_KEY, MAIL_VALUE, CHECK_VALUE],
        ]
    }


def seed_formulas() -> dict[str, list[list[Any]]]:
    """The same table read with ``valueRenderOption=FORMULA``."""
    return {
        SHEET_NAME: [
            [ID_COLUMN, MAIL_COLUMN, CHECK_COLUMN],
            [IDENTITY_KEY, MAIL_VALUE, CHECK_FORMULA],
        ]
    }


class QaSheetsTransport(FakeSheetsTransport):
    """The recorded stand-in plus the one failure mode tests cannot fake.

    ``lost_response`` performs the write for real and only then reports an
    unknown outcome, which is exactly the case the production contract says has
    to be reconciled against the original target instead of resent.

    It applies to the write only. A push reads the header and the identity
    column first, and those reads are separate requests that really did succeed,
    so losing one of their responses would describe a remote state that never
    existed -- the write would never have been sent at all.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.lost_response: SheetsApiError | None = None

    def send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pending = self.lost_response
        if pending is not None and method != "GET":
            self.lost_response = None
        else:
            pending = None
        result = super().send(method, url, params=params, json=json)
        if pending is not None:
            raise pending
        return result


class FileCredentialStore:
    """A ``CredentialStore`` that keeps secrets in the throw-away QA data dir.

    The protocol is the production one; only the backing medium changes, so an
    automated run never touches the operating-system keychain.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def _read_all(self) -> dict[str, str]:
        try:
            payload = json.loads(self._path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def read(self, key: str) -> bytes | None:
        value = self._read_all().get(key)
        return value.encode("utf-8") if isinstance(value, str) else None

    def write(self, key: str, value: bytes) -> None:
        items = self._read_all()
        items[key] = value.decode("utf-8")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(items), "utf-8")
        self._path.chmod(0o600)

    def delete(self, key: str) -> None:
        items = self._read_all()
        if key not in items:
            return
        items.pop(key)
        self._path.write_text(json.dumps(items), "utf-8")


def qa_router(transport: QaSheetsTransport) -> APIRouter:
    """Test controls that only exist in this sidecar.

    They are declared under the ordinary API prefix so the regular instance
    token guard applies; nothing here is reachable in a production sidecar.
    """

    router = APIRouter(prefix="/api/v1/qa/pm6", include_in_schema=False)

    @router.get("/sheets")
    def read_grid(sheet: str = SHEET_NAME) -> dict[str, Any]:
        if sheet not in transport.ids:
            raise HTTPException(404, f"unknown sheet {sheet}")
        return {
            "spreadsheetId": transport.spreadsheet_id,
            "title": transport.title,
            "sheet": sheet,
            "grid": transport.grid(sheet),
            "writes": transport.changes(),
        }

    @router.post("/sheets/cell")
    async def write_cell(request: Request) -> dict[str, Any]:
        """Impersonate a co-editor changing the remote cell directly.

        One real cell has two render views of the same fact: ``FORMULA`` returns
        the formula that is stored and ``UNFORMATTED_VALUE`` returns what it
        computed to. A co-editor that moved only one of them would hand the push
        and pull code a remote state Google cannot produce, so every view that
        exists for the sheet moves together. ``formula`` defaults to ``value``,
        which is what a literal edit leaves behind in both views.
        """
        body = await request.json()
        sheet = str(body.get("sheet") or SHEET_NAME)
        row = int(body["row"])
        column = int(body["column"])
        if sheet not in transport.ids:
            raise HTTPException(404, f"unknown sheet {sheet}")
        if "value" not in body and "formula" not in body:
            raise HTTPException(422, "value 或 formula 至少要给出一个")
        value = body.get("value", "")
        formula = body.get("formula", value)
        views = [transport.grid(sheet)]
        if transport.ids[sheet] in transport.formulas:
            views.append(transport.formulas[transport.ids[sheet]])
        previous: list[Any] = []
        for view in views:
            while len(view) <= row:
                view.append([])
            while len(view[row]) <= column:
                view[row].append("")
            previous.append(view[row][column])
        replacements = [value, formula] if len(views) > 1 else [value]
        for view, replacement in zip(views, replacements, strict=True):
            view[row][column] = replacement
        return {
            "previous": previous[0],
            "previousFormula": previous[-1],
            "value": value,
            "formula": formula,
        }

    @router.post("/sheets/outage")
    async def next_write_outage(request: Request) -> dict[str, Any]:
        """Make the next write fail *after* leaving the machine.

        ``status=0`` is the provider's "sent, outcome unknown" classification, so
        the command must land in ``unknown`` instead of being retried blindly.
        """
        body = await request.json()
        if body.get("enabled", True):
            transport.fail_writes.append(
                SheetsApiError(0, "timeout", "Google Sheets 未在时限内返回结果。")
            )
            return {"armed": "unknown"}
        transport.fail_writes.clear()
        return {"armed": None}

    @router.post("/sheets/lost-response")
    async def next_write_lost_response(request: Request) -> dict[str, Any]:
        """Apply the write, then lose the response.

        The provider sees ``status=0`` ("sent, outcome unknown"), so the command
        must land in ``unknown`` and only a reconcile may decide the outcome.
        """
        body = await request.json()
        if body.get("enabled", True):
            transport.lost_response = SheetsApiError(
                0, "timeout", "Google Sheets 未在时限内返回结果。"
            )
            return {"armed": "unknown-after-write"}
        transport.lost_response = None
        return {"armed": None}

    @router.post("/sheets/refusal")
    async def next_write_refusal(request: Request) -> dict[str, Any]:
        """Make the next write fail *before* anything was written."""
        body = await request.json()
        if body.get("enabled", True):
            transport.fail_writes.append(
                SheetsApiError(403, "forbidden", "Google 拒绝本次写入。")
            )
            return {"armed": "failed"}
        transport.fail_writes.clear()
        return {"armed": None}

    return router


def create_qa_app(settings: Settings):
    transport = QaSheetsTransport(
        seed_grid(),
        spreadsheet_id=SPREADSHEET_ID,
        title=SPREADSHEET_TITLE,
        formulas=seed_formulas(),
    )
    app = create_app(
        settings,
        credential_store=FileCredentialStore(
            Path(settings.data_dir) / "qa-google-credentials.json"
        ),
        google_tokens=FakeTokenTransport(),
        google_transports=lambda _token: transport,
    )
    app.state.pm6_qa_sheets = transport
    app.include_router(qa_router(transport))
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
