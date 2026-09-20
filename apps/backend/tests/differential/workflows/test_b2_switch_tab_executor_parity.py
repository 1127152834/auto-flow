from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from b2_switch_tab_cases import Page, Session, run_case

from autoflow.application.workflows.executors.switch_tab import SwitchTabExecutor
from autoflow.domain.workflows.browser import BrowserSessionPort
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import redact_browser_url

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_REPOSITORY = REPOSITORY_ROOT / "reference" / "WebRPA"
FROZEN_BACKEND = FROZEN_REPOSITORY / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b2_switch_tab_harness.py")
FROZEN_COMMIT = "5ccb900e8dcf1530aae66f676d87593c416c7ebb"

CASES = [
    "index_variables",
    "index_bad",
    "index_range",
    "title_exact",
    "title_contains",
    "title_startswith",
    "title_endswith",
    "title_regex",
    "title_invalid_regex",
    "title_missing",
    "title_empty",
    "title_error",
    "url_exact",
    "url_contains",
    "url_startswith",
    "url_endswith",
    "url_regex",
    "url_invalid_regex",
    "url_missing",
    "url_empty",
    "next",
    "prev",
    "first",
    "last",
    "next_unknown_current",
    "prev_unknown_current",
    "unsupported",
    "missing_browser",
    "empty_pages",
]


def frozen_result(case: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS), case],
        check=True,
        capture_output=True,
        text=True, encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES)
async def test_switch_tab_matches_frozen_source(case: str) -> None:
    assert await run_case(case, SwitchTabExecutor) == frozen_result(case)


@pytest.mark.asyncio
async def test_switch_tab_redacts_result_url_but_preserves_sensitive_raw_variable() -> (
    None
):
    raw_url = "https://user:password@example.test/path?token=secret&view=full"
    page = Page("p1", "Secret page", raw_url)
    session = Session([page], page)
    context = ExecutionContext(
        browser=cast(BrowserSessionPort, session),
        variables={"target": raw_url},
        sensitive_variables={"target"},
    )

    result = await SwitchTabExecutor().execute(
        {
            "switchMode": "url",
            "matchMode": "exact",
            "tabUrl": "{target}",
            "saveUrlVariable": "selected_url",
        },
        context,
    )

    assert result.success is True
    assert result.data["url"] == redact_browser_url(raw_url)
    assert "password" not in result.data["url"]
    assert "secret" not in result.data["url"]
    assert context.variables["selected_url"] == raw_url
    assert "selected_url" in context.sensitive_variables


@pytest.mark.asyncio
async def test_switch_tab_marks_sensitive_page_url_without_sensitive_input() -> None:
    raw_url = "https://example.test/path?token=secret"
    page = Page("p1", "Secret page", raw_url)
    context = ExecutionContext(
        browser=cast(BrowserSessionPort, Session([page], page))
    )

    result = await SwitchTabExecutor().execute(
        {"switchMode": "index", "tabIndex": 0, "saveUrlVariable": "selected_url"},
        context,
    )

    assert result.success is True
    assert context.variables["selected_url"] == raw_url
    assert "selected_url" in context.sensitive_variables


@pytest.mark.asyncio
async def test_switch_tab_uses_top_level_current_page_when_iframe_is_active() -> None:
    first = Page("p1", "First", "https://first.test")
    second = Page("p2", "Second", "https://second.test")
    third = Page("p3", "Third", "https://third.test")
    session = Session([first, second, third], second)
    session._active = Page("frame", "Frame", "https://frame.test")
    context = ExecutionContext(browser=cast(BrowserSessionPort, session))

    result = await SwitchTabExecutor().execute({"switchMode": "next"}, context)

    assert result.success is True
    assert result.data["index"] == 2
    assert session.current_page() is third


def test_differential_checkout_is_the_declared_frozen_commit() -> None:
    actual = subprocess.run(
        ["git", "-C", str(FROZEN_REPOSITORY), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual == FROZEN_COMMIT
