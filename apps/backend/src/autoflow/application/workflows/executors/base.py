from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext


@dataclass(slots=True)
class ModuleResult:
    success: bool
    message: str = ""
    data: Any = None
    error: str | None = None
    branch: str | None = None
    duration: float = 0
    log_level: str | None = None
    skipped: bool = False
    is_timeout: bool = False
    target_node_id: str | None = None


class ModuleExecutor(ABC):
    requires_browser = False

    @staticmethod
    async def stop_process(process: Any, context: ExecutionContext) -> None:
        if context.process_cleanup is not None:
            await context.process_cleanup(process)
        else:
            if process.returncode is None:
                process.kill()
            await process.wait()

    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        del config
        return self.requires_browser

    @property
    @abstractmethod
    def module_type(self) -> str: ...

    @abstractmethod
    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult: ...

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        return True, ""

    def get_text(self, value: Any, context: ExecutionContext) -> str:
        resolved = context.resolve_value(value)
        return str(resolved) if resolved is not None else ""
