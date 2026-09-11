from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from autoflow.application.kernels.operations import KernelOperation
from autoflow.application.kernels.service import KernelService
from autoflow.domain.kernels.errors import (
    KernelDefaultConflict,
    KernelNotFound,
    KernelPathInvalid,
)
from autoflow.domain.kernels.models import (
    DefaultKernel,
    InstalledKernel,
    KernelCatalog,
    KernelRef,
    LicenseStatus,
)
from autoflow.infrastructure.filesystem.kernel_installations import (
    FilesystemKernelInstallationStore,
)
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock


class Catalog:
    def __init__(self, installed: list[InstalledKernel]) -> None:
        self.items = installed

    async def catalog(self) -> KernelCatalog:
        return KernelCatalog("0.5.9", "windows-x64", (), tuple(self.items))

    def installed(self) -> list[InstalledKernel]:
        return list(self.items)

    def is_installed(self, edition: str, version: str) -> bool:
        return any(item.edition == edition and item.version == version for item in self.items)


class License:
    async def status(self) -> LicenseStatus:
        return LicenseStatus(False, False, None, None, None)

    async def connect(self, _key: str) -> LicenseStatus:
        return LicenseStatus(True, True, "pro", None, None)

    def disconnect(self, *, has_active_licensed_operation: bool) -> None:
        assert not has_active_licensed_operation


class Store:
    def read(self) -> str | None:
        return None

    def write(self, _value: str) -> None: ...
    def delete(self) -> None: ...


class Defaults:
    def __init__(self, value: KernelRef | None = None) -> None:
        self.value = DefaultKernel(0, value)
        self.fail_clear = False

    def get(self) -> DefaultKernel:
        return self.value

    def compare_and_set(self, expected_revision: int, kernel: KernelRef | None) -> DefaultKernel:
        if expected_revision != self.value.revision:
            raise KernelDefaultConflict()
        self.value = DefaultKernel(expected_revision + 1, kernel)
        return self.value

    def clear_if_matches(self, kernel: KernelRef) -> DefaultKernel:
        if self.fail_clear:
            raise RuntimeError("database failed")
        if self.value.kernel == kernel:
            self.value = DefaultKernel(self.value.revision + 1, None)
        return self.value


class Installations:
    def __init__(self) -> None:
        self.staged: list[str] = []
        self.restored: list[str] = []
        self.purged: list[str] = []

    @contextmanager
    def guard(self):
        yield

    def stage(self, kernel: KernelRef) -> str:
        token = f"token-{kernel.version}"
        self.staged.append(token)
        return token

    def restore(self, token: str) -> None:
        self.restored.append(token)

    def purge(self, token: str) -> None:
        self.purged.append(token)


class Operations:
    async def start(self, _job):
        raise AssertionError

    async def cancel(self, _operation_id: str):
        raise AssertionError

    def snapshot(self) -> list[KernelOperation]:
        return []


def service(default: KernelRef | None = None):
    ref = KernelRef("public", "146.0.7680.80")
    installed = InstalledKernel(ref.edition, ref.version, Path("/kernels/chrome.exe"), 1)
    defaults = Defaults(default)
    installations = Installations()
    return (
        KernelService(Catalog([installed]), License(), Store(), defaults, installations, Operations()),
        ref,
        defaults,
        installations,
    )


def test_default_compare_and_set_rejects_stale_revision_and_missing_kernel() -> None:
    subject, ref, _, _ = service()

    assert subject.set_default(0, ref) == DefaultKernel(1, ref)
    with pytest.raises(KernelDefaultConflict):
        subject.set_default(0, ref)
    with pytest.raises(KernelNotFound):
        subject.set_default(1, KernelRef("licensed", "151.0.7922.108"))


def test_delete_clears_matching_default_and_preserves_profile_references() -> None:
    ref = KernelRef("public", "146.0.7680.80")
    subject, ref, defaults, installations = service(ref)

    result = subject.remove(ref)

    assert result == DefaultKernel(1, None)
    assert defaults.value.kernel is None
    assert installations.purged == [f"token-{ref.version}"]


def test_delete_restores_staged_install_when_default_transaction_fails() -> None:
    ref = KernelRef("public", "146.0.7680.80")
    subject, ref, defaults, installations = service(ref)
    defaults.fail_clear = True

    with pytest.raises(RuntimeError, match="database failed"):
        subject.remove(ref)

    assert installations.restored == [f"token-{ref.version}"]
    assert installations.purged == []


def test_startup_recovery_restores_an_orphaned_staged_deletion(tmp_path: Path) -> None:
    root = tmp_path / "kernels"
    install = root / "chromium-146.0.7680.80"
    executable = install / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"kernel")
    store = FilesystemKernelInstallationStore(root)
    with store.guard():
        token = store.stage(KernelRef("public", "146.0.7680.80"))
    assert not install.exists()
    assert (root / ".trash" / token).exists()

    recovered = FilesystemKernelInstallationStore(root)
    with recovered.guard():
        recovered.retry_pending()

    assert executable.read_bytes() == b"kernel"
    assert list((root / ".trash").iterdir()) == []


def test_kernel_removal_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "kernels"
    outside = tmp_path / "outside"
    outside.mkdir()
    install = root / "chromium-146.0.7680.80"
    install.mkdir(parents=True)
    (install / "escape").symlink_to(outside, target_is_directory=True)
    store = FilesystemKernelInstallationStore(root)

    with pytest.raises(KernelPathInvalid, match="Managed kernel path is invalid"):
        store.stage(KernelRef("public", "146.0.7680.80"))


def test_default_and_delete_guard_conflict_with_an_active_install(tmp_path: Path) -> None:
    root = tmp_path / "kernels"
    store = FilesystemKernelInstallationStore(root)
    install_lock = ExclusiveFileLock(root / ".install.lock")
    assert install_lock.acquire()
    try:
        from autoflow.domain.kernels.errors import KernelBusy

        with pytest.raises(KernelBusy), store.guard():
            pass
    finally:
        install_lock.release()
