"""Approved WebRPA visual no-op executors.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/{basic,note}.py. Licensed under LICENSE.WebRPA.
"""

from __future__ import annotations

from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor


@register_executor
class GroupExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "group"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        del config, context
        return ModuleResult(success=True, message="备注分组（跳过）")


@register_executor
class NoteExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "note"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        del config, context
        return ModuleResult(success=True, message="便签（跳过）")


VISUAL_EXECUTORS: tuple[type[ModuleExecutor], ...] = (GroupExecutor, NoteExecutor)
