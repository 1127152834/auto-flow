from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[5]
HARNESS = Path(__file__).with_name("frozen_b6_element_change_trigger_harness.py")


def source(payload: dict[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "reference" / "WebRPA" / "backend")
    completed = subprocess.run(
        [sys.executable, str(HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


class Locator:
    @property
    def first(self) -> Locator:
        return self

    async def wait_for(self, **_options: Any) -> None:
        return None


class Page:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def locator(self, _selector: str) -> Locator:
        return Locator()

    async def evaluate(self, _expression: str) -> dict[str, Any]:
        return self.result


class Browser:
    def __init__(self, page: Page) -> None:
        self.page = page

    def active_page(self) -> Page:
        return self.page


@pytest.mark.asyncio
async def test_element_change_validation_matches_frozen_source() -> None:
    executor = build_production_executor_registry().get("element_change_trigger")
    assert executor is not None
    result = await executor.execute({}, ExecutionContext())
    assert {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": {},
    } == source({"config": {}})


@pytest.mark.asyncio
async def test_element_change_success_matches_frozen_source() -> None:
    observer = {
        "success": True,
        "changes": [{"type": "childList", "addedCount": 1, "removedCount": 0}],
        "addedNodes": [
            {"tagName": "li", "className": "item", "id": "new", "textContent": "新增"}
        ],
        "removedNodes": [],
        "newElementSelector": "#new",
        "newElementText": "新增",
        "currentChildCount": 2,
        "initialChildCount": 1,
        "mutationCount": 1,
    }
    payload = {
        "config": {
            "selector": "#list",
            "observeType": "childList",
            "timeout": 5,
            "saveNewElementSelector": "new_selector",
            "saveChangeInfo": "change",
        },
        "observer": observer,
    }
    context = ExecutionContext(browser=Browser(Page(observer)))  # type: ignore[arg-type]
    executor = build_production_executor_registry().get("element_change_trigger")
    assert executor is not None
    result = await executor.execute(payload["config"], context)

    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }
    expected = source(payload)
    target["data"]["timestamp"] = "<timestamp>"
    target["variables"]["change"]["timestamp"] = "<timestamp>"
    expected["data"]["timestamp"] = "<timestamp>"
    expected["variables"]["change"]["timestamp"] = "<timestamp>"
    assert target == expected
