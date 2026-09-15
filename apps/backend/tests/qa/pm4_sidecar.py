"""Isolated PM4 management QA sidecar.

This module is reachable only through the desktop development-only QA switch. It
keeps the production bootstrap unchanged and replaces only project batch
dispatch with the deterministic PM4 runner.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.parent import watch_parent
from autoflow.bootstrap.ready import ready_line
from autoflow.domain.project_automations.models import AutomationRecord
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from tests.qa.pm4_fake_executor import CREATE_ACCOUNT
from tests.qa.pm4_v1_runner import PM4V1FakeRunner

_LOG = logging.getLogger(__name__)
_F_FORCE_STOP_GRACE = timedelta(seconds=2)


def _f_force_stop_projection(
    batch_status: str,
    stop_accepted_at: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[bool, datetime | None]:
    """Project a short F-only grace gate for the deliberately suspended fake runner."""
    if batch_status not in {"stopping", "reconciling"} or stop_accepted_at is None:
        return False, None
    accepted_at = (
        stop_accepted_at.replace(tzinfo=UTC)
        if stop_accepted_at.tzinfo is None
        else stop_accepted_at.astimezone(UTC)
    )
    available_at = accepted_at + _F_FORCE_STOP_GRACE
    current = now or datetime.now(UTC)
    return current >= available_at, available_at


def _f_force_stop_availability(
    factory: sessionmaker[Session],
    project_id: str,
    batch_id: str,
) -> tuple[bool, datetime | None]:
    with factory() as session:
        batch = session.get(ProjectBatchRow, batch_id)
        if batch is None or batch.project_id != project_id:
            return False, None
        operations = session.scalars(
            select(ProjectOperationRow)
            .where(
                ProjectOperationRow.project_id == project_id,
                ProjectOperationRow.kind == "stopBatch",
                ProjectOperationRow.status == "running",
            )
            .order_by(ProjectOperationRow.created_at.desc())
        ).all()
        accepted_at = next(
            (
                operation.created_at
                for operation in operations
                if operation.resource.get("batchId") == batch_id
            ),
            None,
        )
        return _f_force_stop_projection(batch.status, accepted_at)


class _RunnerLoop:
    def __init__(self, runner: PM4V1FakeRunner) -> None:
        self.runner = runner
        self.event = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.closed = False

    async def startup(self) -> None:
        if self.task is None:
            self.closed = False
            self.task = asyncio.create_task(self._run())

    def wake(self) -> None:
        self.event.set()

    async def shutdown(self) -> None:
        self.closed = True
        self.wake()
        if self.task is not None:
            await self.task
            self.task = None

    async def _run(self) -> None:
        while not self.closed:
            self.event.clear()
            try:
                while await self.runner.tick() is not None:
                    pass
            except Exception:  # noqa: BLE001 - QA keeps durable failure evidence
                _LOG.exception("PM4 QA runner could not advance a persisted task")
            try:
                await asyncio.wait_for(self.event.wait(), timeout=0.5)
            except TimeoutError:
                pass


def _create_targets(
    session: Session, automation: AutomationRecord
) -> Sequence[tuple[str, str]]:
    rows = session.scalars(
        select(DataTableRow).where(
            DataTableRow.project_id == automation.project_id,
            DataTableRow.name == "账号",
            DataTableRow.published.is_(True),
        )
    ).all()
    if len(rows) != 1:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE",
            "PM4 V1 requires exactly one published account table 账号 before launch",
            409,
        )
    status_input_id = _status_inputs(automation)[0]
    status_input = next(
        item
        for item in automation.input_plan.get("inputs", [])
        if item.get("inputId") == status_input_id
    )
    statuses = session.scalars(
        select(DataStatusRow).where(
            DataStatusRow.project_id == automation.project_id,
            DataStatusRow.table_id == status_input.get("tableId"),
            DataStatusRow.name == "已使用",
            DataStatusRow.deleted.is_(False),
        )
    ).all()
    if len(statuses) != 1:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE",
            "PM4 V1 requires exactly one email status 已使用 before launch",
            409,
        )
    return ((rows[0].id, rows[0].current_generation),)


def _status_inputs(automation: AutomationRecord) -> Sequence[str]:
    matches = [
        item["inputId"]
        for item in automation.input_plan.get("inputs", [])
        if "邮箱" in str(item.get("alias", ""))
        or "email" in str(item.get("alias", "")).casefold()
    ]
    if len(matches) != 1:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE",
            "PM4 V1 requires exactly one email input grant before launch",
            409,
        )
    return tuple(matches)


def _b_capability_manifest(
    session: Session, automation: AutomationRecord
) -> dict[str, list[dict[str, object]]]:
    accounts = session.scalars(
        select(DataTableRow).where(
            DataTableRow.project_id == automation.project_id,
            DataTableRow.name == "账号",
            DataTableRow.published.is_(True),
        )
    ).all()
    if len(accounts) != 1:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE",
            "PM4-B requires exactly one published account table 账号",
            409,
        )
    account = accounts[0]
    field_ids = list(
        session.scalars(
            select(DataFieldRow.id)
            .where(
                DataFieldRow.project_id == automation.project_id,
                DataFieldRow.table_id == account.id,
                DataFieldRow.dataset_generation == account.current_generation,
            )
            .order_by(DataFieldRow.position, DataFieldRow.id)
        )
    )
    return {
        "tableGrants": [
            {
                "tableId": account.id,
                "datasetGeneration": account.current_generation,
                "operations": [
                    "readRecord",
                    "queryRecords",
                    "updateRecord",
                    "deleteRecord",
                    "addField",
                    "ensureField",
                    "modifyField",
                ],
                "fieldIds": field_ids,
                "readPurposes": ["workflow"],
            }
        ]
    }


def _is_account_reader(automation: AutomationRecord) -> bool:
    inputs = automation.input_plan.get("inputs", [])
    if len(inputs) != 1 or not isinstance(inputs[0], dict):
        return False
    alias = str(inputs[0].get("alias", "")).casefold()
    return "账号" in alias or "account" in alias


def _f_create_targets(
    session: Session, automation: AutomationRecord
) -> Sequence[tuple[str, str]]:
    return () if _is_account_reader(automation) else _create_targets(session, automation)


def _f_status_inputs(automation: AutomationRecord) -> Sequence[str]:
    return () if _is_account_reader(automation) else _status_inputs(automation)


def _f_capability_manifest(
    session: Session, automation: AutomationRecord
) -> dict[str, list[dict[str, object]]]:
    if not _is_account_reader(automation):
        return {"tableGrants": []}
    item = automation.input_plan["inputs"][0]
    table = session.get(DataTableRow, item["tableId"])
    if (
        table is None
        or table.project_id != automation.project_id
        or table.current_generation != item["datasetGeneration"]
        or not table.published
    ):
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE",
            "PM4-F account reader requires the current published account table",
            409,
        )
    field_ids = list(
        session.scalars(
            select(DataFieldRow.id)
            .where(
                DataFieldRow.project_id == automation.project_id,
                DataFieldRow.table_id == table.id,
                DataFieldRow.dataset_generation == table.current_generation,
            )
            .order_by(DataFieldRow.position, DataFieldRow.id)
        )
    )
    return {
        "tableGrants": [
            {
                "tableId": table.id,
                "datasetGeneration": table.current_generation,
                "operations": ["readRecord"],
                "fieldIds": field_ids,
                "readPurposes": ["workflow"],
            }
        ]
    }


def create_qa_app(settings: Settings, *, mode: str = "v1"):
    if mode not in {"v1", "b", "f"}:
        raise ValueError(f"unknown PM4 QA mode: {mode}")
    app = create_app(settings)
    coordinator = app.state.project_run_coordinator
    coordinator._capabilities = ("browser.cloakbrowser", "project.data")
    coordinator._resolve_create_record_targets = (
        _f_create_targets if mode == "f" else _create_targets
    )
    coordinator._resolve_status_input_ids = (
        _f_status_inputs if mode == "f" else _status_inputs
    )
    if mode == "b":
        coordinator._resolve_data_capability_manifest = _b_capability_manifest
    elif mode == "f":
        coordinator._resolve_data_capability_manifest = _f_capability_manifest

    scheduler = app.state.project_run_scheduler
    if mode == "f":
        scheduler.force_stop_availability = lambda project_id, batch_id: (
            _f_force_stop_availability(
                app.state.session_factory,
                project_id,
                batch_id,
            )
        )
    app.router.on_startup[:] = [
        handler
        for handler in app.router.on_startup
        if not (
            getattr(handler, "__self__", None) is scheduler
            and getattr(handler, "__name__", "") == "startup"
        )
    ]
    max_auto_tasks_value = os.environ.get("AUTOFLOW_PM4_QA_MAX_AUTO_TASKS")
    max_auto_tasks = int(max_auto_tasks_value) if max_auto_tasks_value else None
    loop = _RunnerLoop(
        PM4V1FakeRunner(
            app.state.session_factory,
            mode="b" if mode == "b" else "v1",
            acknowledgement_loss_steps=(CREATE_ACCOUNT,) if mode == "f" else (),
            max_auto_tasks=max_auto_tasks,
            settle_normal_stops=mode != "f",
        )
    )
    scheduler.wake = loop.wake
    app.state.pm4_qa_runner = loop
    app.router.add_event_handler("startup", loop.startup)
    app.router.add_event_handler("shutdown", loop.shutdown)
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
    app = create_qa_app(settings, mode=os.environ.get("AUTOFLOW_PM4_QA_MODE", "v1"))
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
