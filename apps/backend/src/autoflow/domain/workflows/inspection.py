from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import (
    PreparedWorkflow,
    initial_values,
    resolve_node_config,
)
from autoflow.domain.workflows.validation import workflow_issues


class InspectionLauncher(Protocol):
    async def execute(self, run_id: str, prepared: PreparedWorkflow, profile: Profile,
                      executable: Path, proxy: ProfileBrowserProxy | None, license_key: str | None,
                      on_event: Callable[[dict[str, Any]], Awaitable[None]]) -> dict[str, Any]: ...
    async def command(self, session_id: str, command: dict[str, Any]) -> dict[str, Any]: ...
    async def stop(self, run_id: str) -> None: ...
    async def shutdown(self) -> None: ...
    def busy(self) -> bool: ...


def inspection_target(selector: str, frame_path: list[str], variables: list[dict[str, Any]], literal_paths: list[str] | None = None) -> dict[str, Any]:
    node = {'id': 'inspection', 'type': 'wait_element', 'config': {
        'selector': selector, 'framePath': frame_path, 'timeoutSeconds': 10, 'waitCondition': 'attached',
    }}
    node['literalPaths'] = literal_paths or []
    document = {'nodes': [node], 'edges': [], 'variables': variables}
    issues = workflow_issues(document)
    if issues:
        raise WorkflowError('INSPECTION_TARGET_INVALID', '定位配置或变量初值无效', 422, issues)
    return resolve_node_config(node, initial_values(document))
