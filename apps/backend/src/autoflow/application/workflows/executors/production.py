from __future__ import annotations

from .base import ModuleExecutor
from .basic import (
    ClickElementExecutor,
    GetElementInfoExecutor,
    InputTextExecutor,
    OpenPageExecutor,
    ScreenshotExecutor,
)
from .page_load import PageLoadCompleteExecutor, WaitPageLoadExecutor
from .registry import ExecutorRegistry

PRODUCTION_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    OpenPageExecutor,
    ClickElementExecutor,
    InputTextExecutor,
    GetElementInfoExecutor,
    ScreenshotExecutor,
    WaitPageLoadExecutor,
    PageLoadCompleteExecutor,
)


def build_production_executor_registry() -> ExecutorRegistry:
    registry = ExecutorRegistry()
    for executor in PRODUCTION_EXECUTORS:
        registry.register(executor)
    return registry
