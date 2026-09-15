from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from autoflow.domain.kernels.models import KernelRef
from autoflow.domain.workflows.browser import WorkflowBrowserBusy
from autoflow.infrastructure.filesystem.profile_data import FilesystemProfileUsageGuard
from autoflow.infrastructure.process.workflow_worker import WorkflowResourceCoordinator


@pytest.mark.asyncio
async def test_profile_kernel_and_workspace_remain_owned_until_cleanup_finishes(
    tmp_path: Path,
) -> None:
    profile_id = str(uuid4())
    profile_guard = FilesystemProfileUsageGuard(tmp_path / "profiles")
    first = WorkflowResourceCoordinator(profile_guard, tmp_path / "kernels")
    second = WorkflowResourceCoordinator(profile_guard, tmp_path / "kernels")
    kernel = KernelRef("public", "145.0.7632.109")

    await first.acquire("run-1", profile_id, kernel)

    with pytest.raises(WorkflowBrowserBusy):
        await first.acquire("run-2", str(uuid4()), kernel)
    with pytest.raises(WorkflowBrowserBusy):
        await second.acquire("run-2", profile_id, kernel)
    with pytest.raises(WorkflowBrowserBusy):
        await second.acquire(
            "run-3", str(uuid4()), KernelRef("public", "146.0.1.1")
        )

    await first.release("run-1")
    await second.acquire("run-2", profile_id, kernel)
    await second.release("run-2")


@pytest.mark.asyncio
async def test_wrong_owner_cannot_release_browser_resources(tmp_path: Path) -> None:
    profile_id = str(uuid4())
    coordinator = WorkflowResourceCoordinator(
        FilesystemProfileUsageGuard(tmp_path / "profiles"), tmp_path / "kernels"
    )
    kernel = KernelRef("public", "145.0.7632.109")
    await coordinator.acquire("run-owner", profile_id, kernel)

    with pytest.raises(WorkflowBrowserBusy):
        await coordinator.release("run-other")

    assert coordinator.owner_id == "run-owner"
    await coordinator.release("run-owner")
