"""Remediation M1 AC1-13: press_key against a real CloakBrowser page."""

import os
from pathlib import Path

import pytest
import pytest_asyncio

from autoflow.application.workflows.executors.web_basic import PressKeyExecutor
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import CloakBrowserWorkflowSession

FORM = (
    "data:text/html,<form onsubmit=\"document.title='sent';return false\">"
    "<input id=q autofocus><input id=next><button type=submit>go</button></form>"
)


@pytest_asyncio.fixture
async def real_cloak_context(tmp_path, monkeypatch):
    configured = os.environ.get("AUTOFLOW_TEST_CLOAKBROWSER")
    if not configured:
        pytest.skip("set AUTOFLOW_TEST_CLOAKBROWSER to an installed real CloakBrowser executable")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(Path(configured).resolve(strict=True)))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path / "cache"))
    from cloakbrowser import launch_context_async  # type: ignore[import-untyped]

    context = await launch_context_async(headless=True)
    try:
        yield context
    finally:
        await context.close()


@pytest.mark.asyncio
async def test_enter_on_an_element_submits_and_tab_moves_focus(real_cloak_context):
    page = real_cloak_context.pages[0] if real_cloak_context.pages else await real_cloak_context.new_page()
    await page.goto(FORM)
    context = ExecutionContext(browser=CloakBrowserWorkflowSession(real_cloak_context))
    tab = await PressKeyExecutor().execute({"key": "Tab"}, context)
    assert tab.success, tab.error
    assert await page.evaluate("document.activeElement.id") == "next"
    enter = await PressKeyExecutor().execute(
        {"key": "Enter", "targetType": "element", "selector": "#q"}, context
    )
    assert enter.success, enter.error
    assert await page.title() == "sent"
