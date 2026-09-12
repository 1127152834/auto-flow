from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path

import pytest
from autoflow.application.kernels.operations import KernelOperation
from autoflow.application.kernels.service import KernelService
from autoflow.domain.kernels.errors import (
    KernelBusy,
    KernelDefaultConflict,
    KernelNotFound,
    KernelPathInvalid,
    LicenseInUse,
    LicenseInvalid,
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
    kernel_target_lock,
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
        return any(
            item.edition == edition and item.version == version for item in self.items
        )


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

    def compare_and_set(
        self, expected_revision: int, kernel: KernelRef | None
    ) -> DefaultKernel:
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
    def guard(self, _kernel: KernelRef | None = None):
        yield

    @contextmanager
    def license_guard(self):
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
    installed = InstalledKernel(
        ref.edition, ref.version, Path("/kernels/chrome.exe"), 1
    )
    defaults = Defaults(default)
    installations = Installations()
    return (
        KernelService(
            Catalog([installed]),
            License(),
            Store(),
            defaults,
            installations,
            Operations(),
        ),
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

    recovered = FilesystemKernelInstallationStore(root, platform="windows-x64")
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


def test_delete_guard_conflicts_only_with_the_same_active_install_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "kernels"
    store = FilesystemKernelInstallationStore(root)
    ref = KernelRef("public", "146.0.7680.80")
    target_lock = kernel_target_lock(root, ref.edition, ref.version)
    assert target_lock.acquire()
    try:
        with store.guard():
            pass
        with pytest.raises(KernelBusy), store.guard(ref):
            pass
    finally:
        target_lock.release()


def test_delete_target_guard_releases_reservation_when_maintenance_is_busy(
    tmp_path: Path,
) -> None:
    root = tmp_path / "kernels"
    store = FilesystemKernelInstallationStore(root)
    ref = KernelRef("public", "146.0.7680.80")
    maintenance = ExclusiveFileLock(root / ".install.lock")
    assert maintenance.acquire()
    try:
        with pytest.raises(KernelBusy), store.guard(ref):
            pass
    finally:
        maintenance.release()

    target = kernel_target_lock(root, ref.edition, ref.version)
    assert target.acquire()
    target.release()


def test_startup_does_not_restore_partially_purged_install(tmp_path: Path) -> None:
    root = tmp_path / "kernels"
    trash = root / ".trash"
    token = "0" * 32 + "-chromium-146.0.7680.80"
    partial = trash / token
    partial.mkdir(parents=True)
    (partial / "resources.pak").write_bytes(b"partial")
    store = FilesystemKernelInstallationStore(root, platform="windows-x64")

    with store.guard():
        store.retry_pending()

    assert partial.is_dir()
    assert not (root / "chromium-146.0.7680.80").exists()


class MemoryLicenseStore:
    def __init__(self, key: str | None) -> None:
        self.key = key

    def read(self) -> str | None:
        return self.key

    def write(self, value: str) -> None:
        self.key = value

    def delete(self) -> None:
        self.key = None


class DeletingLicense(License):
    def __init__(self, store: MemoryLicenseStore) -> None:
        self.store = store

    def disconnect(self, *, has_active_licensed_operation: bool) -> None:
        if has_active_licensed_operation:
            raise LicenseInUse()
        self.store.delete()


class PausingOperations(Operations):
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.started_job = None

    async def start(self, job):
        self.entered.set()
        await self.release.wait()
        self.started_job = job
        return KernelOperation.new(
            operation_id="operation-1",
            edition=job.edition,
            requested_version=job.requested_version,
            release_channel=job.release_channel,
        )


@pytest.mark.asyncio
async def test_license_disconnect_cannot_pass_while_download_is_registering(
    tmp_path: Path,
) -> None:
    root = tmp_path / "kernels"
    credentials = MemoryLicenseStore("old-license")
    operations = PausingOperations()
    catalog = Catalog([])
    downloader = KernelService(
        catalog,
        DeletingLicense(credentials),
        credentials,
        Defaults(),
        FilesystemKernelInstallationStore(root, platform="windows-x64"),
        operations,
    )
    disconnector = KernelService(
        catalog,
        DeletingLicense(credentials),
        credentials,
        Defaults(),
        FilesystemKernelInstallationStore(root, platform="windows-x64"),
        Operations(),
    )
    download = asyncio.create_task(
        downloader.download("licensed", "151.0.7922.108", "stable")
    )
    await operations.entered.wait()

    with pytest.raises(LicenseInUse):
        disconnector.disconnect_license()

    operations.release.set()
    await download
    assert operations.started_job.license_key == "old-license"
    assert credentials.key == "old-license"


@pytest.mark.asyncio
async def test_download_cannot_use_deleted_license_when_disconnect_wins(
    tmp_path: Path,
) -> None:
    credentials = MemoryLicenseStore("old-license")
    subject = KernelService(
        Catalog([]),
        DeletingLicense(credentials),
        credentials,
        Defaults(),
        FilesystemKernelInstallationStore(tmp_path / "kernels", platform="windows-x64"),
        Operations(),
    )

    subject.disconnect_license()

    with pytest.raises(LicenseInvalid):
        await subject.download("licensed", "151.0.7922.108", "stable")


@pytest.mark.asyncio
async def test_second_licensed_download_maps_license_gate_contention_to_kernel_busy(
    tmp_path: Path,
) -> None:
    root = tmp_path / "kernels"
    credentials = MemoryLicenseStore("license")
    first_operations = PausingOperations()
    first = KernelService(
        Catalog([]),
        DeletingLicense(credentials),
        credentials,
        Defaults(),
        FilesystemKernelInstallationStore(root, platform="windows-x64"),
        first_operations,
    )
    second = KernelService(
        Catalog([]),
        DeletingLicense(credentials),
        credentials,
        Defaults(),
        FilesystemKernelInstallationStore(root, platform="windows-x64"),
        Operations(),
    )
    running = asyncio.create_task(
        first.download("licensed", "151.0.7922.108", "stable")
    )
    await first_operations.entered.wait()

    with pytest.raises(KernelBusy):
        await second.download("licensed", "151.0.7922.109", "stable")

    first_operations.release.set()
    await running
