from __future__ import annotations

from .base import ModuleExecutor
from .basic import (
    ClickElementExecutor,
    GetElementInfoExecutor,
    InputTextExecutor,
    OpenPageExecutor,
    ScreenshotExecutor,
)
from .data_structure import (
    DictGetExecutor,
    DictKeysExecutor,
    DictOperationExecutor,
    ListExportExecutor,
    ListGetExecutor,
    ListLengthExecutor,
    ListOperationExecutor,
    RegexExtractExecutor,
    StringCaseExecutor,
    StringConcatExecutor,
    StringJoinExecutor,
    StringReplaceExecutor,
    StringSplitExecutor,
    StringSubstringExecutor,
    StringTrimExecutor,
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
    ListOperationExecutor,
    ListGetExecutor,
    ListLengthExecutor,
    ListExportExecutor,
    DictOperationExecutor,
    DictGetExecutor,
    DictKeysExecutor,
    RegexExtractExecutor,
    StringReplaceExecutor,
    StringSplitExecutor,
    StringJoinExecutor,
    StringConcatExecutor,
    StringTrimExecutor,
    StringCaseExecutor,
    StringSubstringExecutor,
)


def build_production_executor_registry() -> ExecutorRegistry:
    registry = ExecutorRegistry()
    for executor in PRODUCTION_EXECUTORS:
        registry.register(executor)
    return registry
