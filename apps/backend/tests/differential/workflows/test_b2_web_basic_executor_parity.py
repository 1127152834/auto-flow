from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from b2_web_basic_cases import Page, Session, run_case

from autoflow.application.workflows.executors.basic import OpenPageExecutor
from autoflow.application.workflows.executors.web_basic import (
    WEB_BASIC_EXECUTORS,
    ClosePageExecutor,
    GoBackExecutor,
    GoForwardExecutor,
    HandleDialogExecutor,
    HoverElementExecutor,
    InjectJavaScriptExecutor,
    RefreshPageExecutor,
    SwitchIframeExecutor,
    SwitchToMainExecutor,
    UseOpenedPageExecutor,
    WaitElementExecutor,
)
from autoflow.domain.workflows.browser import BrowserSessionPort
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_REPOSITORY = REPOSITORY_ROOT / "reference" / "WebRPA"
FROZEN_BACKEND = FROZEN_REPOSITORY / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_b2_web_basic_harness.py")
FROZEN_COMMIT = "5ccb900e8dcf1530aae66f676d87593c416c7ebb"

EXECUTORS = {
    "use_opened_page": UseOpenedPageExecutor,
    "close_page": ClosePageExecutor,
    "refresh_page": RefreshPageExecutor,
    "go_back": GoBackExecutor,
    "go_forward": GoForwardExecutor,
    "switch_iframe": SwitchIframeExecutor,
    "switch_to_main": SwitchToMainExecutor,
    "hover_element": HoverElementExecutor,
    "handle_dialog": HandleDialogExecutor,
    "inject_javascript": InjectJavaScriptExecutor,
    "wait_element": WaitElementExecutor,
}

CASES = [
    "close_page:default",
    "close_page:missing",
    "close_page:error",
    "refresh_page:default",
    "refresh_page:missing",
    "refresh_page:error",
    "go_back:default",
    "go_back:none",
    "go_back:error",
    "go_back:missing",
    "go_forward:default",
    "go_forward:none",
    "go_forward:error",
    "go_forward:missing",
    "hover_element:default",
    "hover_element:hints",
    "hover_element:empty",
    "hover_element:error",
    "hover_element:missing",
    "wait_element:visible",
    "wait_element:hidden",
    "wait_element:attached",
    "wait_element:detached",
    "wait_element:unknown",
    "wait_element:hints",
    "wait_element:empty",
    "wait_element:error",
    "wait_element:missing",
    "handle_dialog:default",
    "handle_dialog:accept",
    "handle_dialog:dismiss",
    "handle_dialog:other",
    "handle_dialog:missing",
    "inject_javascript:current",
    "inject_javascript:all",
    "inject_javascript:partial",
    "inject_javascript:url",
    "inject_javascript:url_empty",
    "inject_javascript:invalid_url",
    "inject_javascript:index",
    "inject_javascript:index_error",
    "inject_javascript:unsupported",
    "inject_javascript:empty",
    "inject_javascript:missing",
    "switch_iframe:index",
    "switch_iframe:range",
    "switch_iframe:name",
    "switch_iframe:name_id",
    "switch_iframe:name_empty",
    "switch_iframe:selector",
    "switch_iframe:selector_not_iframe",
    "switch_iframe:selector_error",
    "switch_iframe:unsupported",
    "switch_iframe:missing",
    "switch_to_main:default",
    "switch_to_main:after_frame",
    "switch_to_main:missing",
    "use_opened_page:default",
    "use_opened_page:title",
    "use_opened_page:url",
    "use_opened_page:skip_bad_title",
    "use_opened_page:navigate",
    "use_opened_page:navigate_empty",
    "use_opened_page:navigate_none",
    "use_opened_page:refresh",
    "use_opened_page:refresh_none",
    "use_opened_page:no_match",
    "use_opened_page:unknown",
    "use_opened_page:missing",
]


def frozen_result(case: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS), case],
        check=True,
        capture_output=True,
        text=True, encoding="utf-8",
        env={"PYTHONPATH": str(FROZEN_BACKEND)},
    )
    return json.loads(completed.stdout)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES)
async def test_web_basic_executor_matches_frozen_source(case: str) -> None:
    assert await run_case(case, EXECUTORS) == frozen_result(case)


def test_differential_checkout_is_the_declared_frozen_commit() -> None:
    actual = subprocess.run(
        ["git", "-C", str(FROZEN_REPOSITORY), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual == FROZEN_COMMIT


def test_web_basic_executor_list_contains_exactly_the_approved_family() -> None:
    assert {executor().module_type for executor in WEB_BASIC_EXECUTORS} == set(
        EXECUTORS
    )


@pytest.mark.asyncio
async def test_iframe_state_works_with_the_slotted_autoflow_execution_context() -> None:
    main = Page("main", "https://main.test", "Main")
    frame = Page("frame", "https://frame.test", "Frame")
    main.frames.append(frame)
    session = Session([main])
    context = ExecutionContext(browser=cast(BrowserSessionPort, session))

    switched = await SwitchIframeExecutor().execute(
        {"locateBy": "index", "iframeIndex": 0}, context
    )
    hovered = await HoverElementExecutor().execute(
        {"selector": "#inside", "hoverDuration": 0}, context
    )
    restored = await SwitchToMainExecutor().execute({}, context)

    assert switched.success is True
    assert hovered.success is True
    assert frame.calls[-1][0] == "hover"
    assert restored.message == "已切换回主页面，URL: https://main.test"


@pytest.mark.asyncio
async def test_web_basic_calls_autoflow_ports_with_millisecond_timeouts() -> None:
    calls: list[tuple[str, Any]] = []

    class StrictLocator:
        async def wait_for(
            self, *, state: str = "visible", timeout_ms: float | None = None
        ) -> None:
            calls.append(("wait", (state, timeout_ms)))

        async def hover(
            self, *, force: bool = False, timeout_ms: float | None = None
        ) -> None:
            calls.append(("hover", (force, timeout_ms)))

    class StrictPage(Page):
        def locator(self, selector: str) -> StrictLocator:
            calls.append(("locator", selector))
            return StrictLocator()

        async def goto(self, url: str, *, wait_until: str, timeout_ms: float) -> object:
            calls.append(("goto", (url, wait_until, timeout_ms)))
            self.url = url
            return object()

    page = StrictPage("strict", "https://strict.test", "Strict")
    session = Session([page])
    context = ExecutionContext(browser=cast(BrowserSessionPort, session))

    hovered = await HoverElementExecutor().execute(
        {"selector": "#target", "hoverDuration": 0, "timeout": 2}, context
    )
    navigated = await UseOpenedPageExecutor().execute(
        {"action": "navigate", "url": "https://target.test"}, context
    )

    assert hovered.success is True
    assert navigated.success is True
    assert calls == [
        ("locator", "#target"),
        ("wait", ("attached", 2000)),
        ("hover", (False, 2000)),
        ("goto", ("https://target.test", "load", 60000)),
    ]


@pytest.mark.asyncio
async def test_injected_javascript_does_not_expose_sensitive_variables() -> None:
    page = Page("secure", "https://secure.test", "Secure")
    context = ExecutionContext(
        browser=cast(BrowserSessionPort, Session([page])),
        variables={"public_value": 7, "password": "S3CRET"},
        sensitive_variables={"password"},
    )

    result = await InjectJavaScriptExecutor().execute(
        {"javascriptCode": "return vars.public_value", "injectMode": "current"},
        context,
    )

    assert result.success is True
    evaluated_code = next(call[1] for call in page.calls if call[0] == "evaluate")
    assert '"public_value": 7' in evaluated_code
    assert "password" not in evaluated_code
    assert "S3CRET" not in evaluated_code


@pytest.mark.asyncio
async def test_opened_page_result_redacts_url_credentials_and_sensitive_query() -> None:
    page = Page(
        "secure",
        "https://user:password@secure.test/callback?token=S3CRET&view=summary",
        "Secure",
    )
    context = ExecutionContext(
        browser=cast(BrowserSessionPort, Session([page]))
    )

    result = await UseOpenedPageExecutor().execute({"action": "use"}, context)

    assert result.success is True
    rendered = json.dumps(
        {"message": result.message, "data": result.data}, ensure_ascii=False
    )
    assert "password" not in rendered
    assert "S3CRET" not in rendered
    assert "%5B%E5%B7%B2%E9%9A%90%E8%97%8F%5D" in rendered


@pytest.mark.asyncio
async def test_open_page_failure_redacts_url_from_provider_error() -> None:
    raw_url = "https://user:password@secure.test/start?token=S3CRET"

    class FailingPage(Page):
        async def goto(self, url: str, **options: Any) -> object | None:
            raise RuntimeError(f"navigation failed for {url}")

        async def bring_to_front(self) -> None:
            return None

    page = FailingPage("secure", "about:blank", "Secure")
    context = ExecutionContext(
        browser=cast(BrowserSessionPort, Session([page]))
    )

    result = await OpenPageExecutor().execute(
        {"url": raw_url, "openMode": "current_tab"}, context
    )

    assert result.success is False
    assert "password" not in (result.error or "")
    assert "S3CRET" not in (result.error or "")
    assert "secure.test/start" in (result.error or "")
