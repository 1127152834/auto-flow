from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from autoflow.application.kernels.service import KernelService
from autoflow.application.profiles.service import ProfileService
from autoflow.domain.kernels.errors import KernelBusy
from autoflow.domain.kernels.models import DefaultKernel, InstalledKernel, KernelRef
from autoflow.domain.profiles.errors import ProfileDirectoryBusy
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.domain.workflows.browser import WorkflowBrowserBusy
from autoflow.infrastructure.database.profiles import profile_repository_transaction
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.kernel_installations import (
    FilesystemKernelInstallationStore,
)
from autoflow.infrastructure.filesystem.profile_data import (
    FilesystemProfileDataStore,
    FilesystemProfileUsageGuard,
)
from autoflow.infrastructure.process.workflow_worker import WorkflowResourceCoordinator


class _InstalledResources:
    def __init__(self, kernel: InstalledKernel) -> None:
        self.kernel = kernel

    def is_installed(self, edition: str, version: str) -> bool:
        return edition == self.kernel.edition and version == self.kernel.version


class _NoProxies:
    def proxy_is_available(self, _proxy_id: str) -> bool:
        return False

    def pool_exists(self, _pool_id: str) -> bool:
        return False


class _KernelDefaults:
    def __init__(self, ref: KernelRef) -> None:
        self.value = DefaultKernel(0, ref)

    def get(self) -> DefaultKernel:
        return self.value

    def clear_if_matches(self, ref: KernelRef) -> DefaultKernel:
        if self.value.kernel == ref:
            self.value = DefaultKernel(self.value.revision + 1, None)
        return self.value

    def compare_and_set(
        self, expected_revision: int, ref: KernelRef | None
    ) -> DefaultKernel:
        self.value = DefaultKernel(expected_revision + 1, ref)
        return self.value


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


@pytest.mark.asyncio
async def test_active_workflow_blocks_profile_and_kernel_deletion_until_cleanup(
    tmp_path: Path,
) -> None:
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    profile_root = tmp_path / "profiles"
    kernels_root = tmp_path / "kernels"
    version = "145.0.7632.109"
    ref = KernelRef("public", version)
    kernel_dir = kernels_root / f"chromium-{version}"
    kernel_dir.mkdir(parents=True)
    executable = kernel_dir / "CloakBrowser"
    executable.write_bytes(b"managed kernel")
    installed = InstalledKernel("public", version, executable, executable.stat().st_size)
    profile_guard = FilesystemProfileUsageGuard(profile_root)
    profile_data = FilesystemProfileDataStore(profile_root)
    profiles = ProfileService(
        lambda: profile_repository_transaction(sessions),
        _InstalledResources(installed),
        _NoProxies(),
        profile_guard,
        profile_data,
    )
    profile = profiles.create(
        ProfileSpec.from_values(
            {"name": "运行占用", "browser_version": version, "browser_edition": "public"}
        )
    )
    profile_dir = profile_root / profile.id
    profile_dir.mkdir()
    (profile_dir / "Preferences").write_text("{}", encoding="utf-8")
    defaults = _KernelDefaults(ref)
    installations = FilesystemKernelInstallationStore(kernels_root)
    unused: Any = object()
    kernels = KernelService(
        _InstalledResources(installed), unused, unused, defaults, installations, unused
    )
    resources = WorkflowResourceCoordinator(profile_guard, kernels_root)

    await resources.acquire("run-active", profile.id, ref)

    with pytest.raises(ProfileDirectoryBusy):
        profiles.remove(profile.id)
    with pytest.raises(KernelBusy):
        kernels.remove(ref)
    assert profiles.get(profile.id) == profile
    assert profile_dir.is_dir()
    assert kernel_dir.is_dir()

    await resources.release("run-active")
    profiles.remove(profile.id)
    removed_default = kernels.remove(ref)

    assert profiles.list() == []
    assert not profile_dir.exists()
    assert not kernel_dir.exists()
    assert removed_default.kernel is None
