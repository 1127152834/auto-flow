"""Surface failed test ids and reasons as GitHub annotations.

Job logs are not always readable by the people triaging a CI failure, while
annotations are. Inside GitHub Actions this plugin prints a few error
annotations at the end of the session listing every failed test with the first
line of its reason. It never changes outcomes and is inert elsewhere.
"""

from __future__ import annotations

import os

import pytest

LIMIT = 3_500  # GitHub shows about 4 KB of an annotation message
MAX_ANNOTATIONS = 6


def _escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def render(failures: list[tuple[str, str]]) -> list[str]:
    """Group `(nodeid, reason)` pairs into size-bounded annotation lines."""
    chunks: list[str] = []
    current = ""
    for nodeid, reason in failures:
        line = f"{nodeid} :: {reason}".replace("\n", " ")[:600] + "\n"
        if current and len(current) + len(line) > LIMIT:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    shown = chunks[:MAX_ANNOTATIONS]
    annotations = [
        f"::error title=failed tests ({index + 1}/{len(chunks)})::{_escape(chunk)}"
        for index, chunk in enumerate(shown)
    ]
    if len(chunks) > len(shown):
        omitted = sum(chunk.count("\n") for chunk in chunks[len(shown) :])
        annotations.append(f"::error title=more failed tests::{omitted} more not listed")
    return annotations


class _Collector:
    def __init__(self) -> None:
        self.failures: list[tuple[str, str]] = []

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if not report.failed:
            return
        crash = getattr(report.longrepr, "reprcrash", None)
        reason = getattr(crash, "message", None) or str(report.longrepr)[-300:]
        self.failures.append((f"{report.nodeid} [{report.when}]", reason))

    def pytest_sessionfinish(self) -> None:
        for annotation in render(self.failures):
            # pytest's progress line has no trailing newline; commands only parse at line start.
            print("\n" + annotation, flush=True)


def pytest_configure(config: pytest.Config) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        config.pluginmanager.register(_Collector(), "autoflow-ci-annotations")
