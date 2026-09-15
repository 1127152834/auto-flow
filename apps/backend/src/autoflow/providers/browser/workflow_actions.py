from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.browser import BrowserLocatorPort, BrowserPagePort


def fallback_selectors(hints: Mapping[str, Any] | None) -> list[str]:
    if not hints:
        return []
    result: list[str] = []
    attributes = hints.get("attributes")
    attrs = attributes if isinstance(attributes, Mapping) else {}
    tag_value = hints.get("tag") or hints.get("tagName") or ""
    tag = tag_value.strip().lower() if isinstance(tag_value, str) else ""

    def text_value(*keys: str) -> str:
        for key in keys:
            value = hints.get(key, attrs.get(key))
            if isinstance(value, str) and value:
                return value
        return ""

    def add(selector: str) -> None:
        if selector and selector not in result:
            result.append(selector)

    test_id = text_value("testid", "data-testid")
    element_id = text_value("id")
    name = text_value("name")
    placeholder = text_value("placeholder")
    aria = text_value("ariaLabel", "aria-label")
    text = text_value("text").strip()
    class_name = text_value("className").strip()
    if test_id:
        add(f'[data-testid="{test_id}"]')
    if element_id and re.match(r"^[A-Za-z][\w-]*$", element_id):
        add(f"#{element_id}")
    if name:
        add(f'{tag or "*"}[name="{name}"]')
    if placeholder:
        add(f'[placeholder="{placeholder}"]')
    if aria:
        add(f'[aria-label="{aria}"]')
    if text and len(text) <= 40:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        add(f'{tag or "*"}:has-text("{escaped}")')
        add(f'text="{escaped}"')
    if class_name and " " not in class_name and re.match(
        r"^[A-Za-z][\w-]*$", class_name
    ):
        add(f"{tag}.{class_name}" if tag else f".{class_name}")
    return result


async def wait_for_locator(
    page: BrowserPagePort,
    selector: str,
    *,
    state: str,
    timeout_ms: float | None,
    hints: Mapping[str, Any] | None = None,
) -> tuple[BrowserLocatorPort, str]:
    locator = page.locator(selector)
    try:
        await locator.wait_for(state=state, timeout_ms=timeout_ms)
        return locator, selector
    except Exception:
        for fallback in fallback_selectors(hints):
            candidate = page.locator(fallback)
            try:
                await candidate.wait_for(state=state, timeout_ms=3000)
                return candidate, fallback
            except Exception:  # noqa: BLE001,S112 -- try the next frozen candidate.
                continue
        raise
