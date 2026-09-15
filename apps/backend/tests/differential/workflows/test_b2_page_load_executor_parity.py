from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from autoflow.application.workflows.executors.page_load import (
    PageLoadCompleteExecutor,
    WaitPageLoadExecutor,
)
from autoflow.domain.workflows.browser import BrowserSessionPort
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b2_page_load_harness.py")
FROZEN_COMMIT = "5ccb900e8dcf1530aae66f676d87593c416c7ebb"


def frozen_result(case: str) -> dict[str, Any]:
    actual_commit = subprocess.run(
        ["git", "-C", str(FROZEN_BACKEND.parent), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual_commit == FROZEN_COMMIT
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS), case],
        check=True,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout)


class Page:
    id = "page-1"
    url = "https://fixture.test"
    closed = False

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[Any]] = []

    async def wait_for_load_state(self, state: str, *, timeout_ms: float) -> None:
        self.calls.append([state, timeout_ms])
        if self.fail:
            raise TimeoutError("fixture timeout")


class Session:
    def __init__(self, page: Page) -> None:
        self.page = page

    def current_page(self) -> Page:
        return self.page


class FailingSession:
    def current_page(self) -> Page:
        raise RuntimeError("fixture current page is closed")


class FailingContext(ExecutionContext):
    def set_variable(self, name: str, value: Any) -> None:
        raise RuntimeError("fixture variable write failed")


async def migrated_result(case: str) -> dict[str, Any]:
    if case == "missing":
        context = ExecutionContext()
        wait_result = await WaitPageLoadExecutor().execute({}, context)
        status_result = await PageLoadCompleteExecutor().execute({}, context)
        return {"errors": [wait_result.error, status_result.error]}

    fail = case in {"wait_failure", "status_pending"}
    page = Page(fail=fail)
    context_type = (
        FailingContext if case == "status_write_failure" else ExecutionContext
    )
    variables = (
        {}
        if case in {"wait_default", "status_default", "status_write_failure"}
        else {"state": "networkidle", "seconds": 2.5}
    )
    context = context_type(
        browser=cast(BrowserSessionPort, Session(page)),
        variables=variables,
    )
    if case.startswith("wait_"):
        config = (
            {}
            if case == "wait_default"
            else {"waitUntil": "{state}", "timeout": "{seconds}"}
        )
        result = await WaitPageLoadExecutor().execute(config, context)
    else:
        config = (
            {}
            if case in {"status_default", "status_write_failure"}
            else {"checkState": "{state}", "saveToVariable": "{status_name}"}
        )
        result = await PageLoadCompleteExecutor().execute(config, context)
    return {
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "data": result.data,
        "calls": page.calls,
        "variables": context.variables,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["wait_default", "wait_success", "wait_failure"])
async def test_wait_page_load_matches_frozen_source(case: str) -> None:
    assert await migrated_result(case) == frozen_result(case)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    ["status_default", "status_loaded", "status_pending", "status_write_failure"],
)
async def test_page_load_complete_matches_frozen_source(case: str) -> None:
    assert await migrated_result(case) == frozen_result(case)


@pytest.mark.asyncio
async def test_page_load_family_preserves_missing_page_errors() -> None:
    assert await migrated_result("missing") == frozen_result("missing")


@pytest.mark.asyncio
async def test_closed_current_page_uses_autoflow_missing_page_contract() -> None:
    context = ExecutionContext(browser=cast(BrowserSessionPort, FailingSession()))

    wait_result = await WaitPageLoadExecutor().execute({}, context)
    status_result = await PageLoadCompleteExecutor().execute({}, context)

    assert wait_result.error == "页面未打开"
    assert status_result.error == "页面未打开"


def test_differential_checkout_is_the_declared_frozen_commit() -> None:
    actual_commit = subprocess.run(
        ["git", "-C", str(FROZEN_BACKEND.parent), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert actual_commit == FROZEN_COMMIT
