import logging
import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from autoflow.domain.kernels.errors import (
    KernelBusy,
    KernelNotFound,
    KernelPathInvalid,
    LicenseInUse,
)
from autoflow.domain.kernels.models import KernelRef
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock
from autoflow.providers.kernel.catalog import (
    current_platform_tag,
    executable_path,
    is_valid_kernel_version,
)

logger = logging.getLogger(__name__)
_TOKEN = re.compile(r"[0-9a-f]{32}-chromium-[0-9]+(?:\.[0-9]+){3,4}(?:-pro)?")


class FilesystemKernelInstallationStore:
    def __init__(self, root: Path, *, platform: str | None = None) -> None:
        absolute = Path(root).absolute()
        if absolute.is_symlink():
            raise KernelPathInvalid()
        absolute.mkdir(parents=True, exist_ok=True)
        self.root = absolute.resolve()
        self.trash = self.root / ".trash"
        if self.trash.is_symlink():
            raise KernelPathInvalid()
        self.trash.mkdir(exist_ok=True)
        self.platform = platform or current_platform_tag()

    @contextmanager
    def guard(self, kernel: KernelRef | None = None) -> Iterator[None]:
        self._ensure_roots()
        target_lock = (
            kernel_target_lock(self.root, kernel.edition, kernel.version)
            if kernel is not None
            else None
        )
        lock = ExclusiveFileLock(self.root / ".install.lock")
        try:
            try:
                if target_lock is not None and not target_lock.acquire():
                    raise KernelBusy()
                if not lock.acquire():
                    raise KernelBusy()
            except OSError:
                raise KernelBusy() from None
            yield
        finally:
            lock.release()
            if target_lock is not None:
                target_lock.release()

    @contextmanager
    def license_guard(self) -> Iterator[None]:
        lock = ExclusiveFileLock(self.root / ".license.lock")
        try:
            if not lock.acquire():
                raise LicenseInUse()
        except OSError:
            raise LicenseInUse() from None
        try:
            yield
        finally:
            lock.release()

    def stage(self, kernel: KernelRef) -> str:
        source = self._kernel_path(kernel)
        if not source.exists():
            raise KernelNotFound()
        self._validate_tree(source)
        token = f"{uuid4().hex}-{source.name}"
        try:
            source.rename(self.trash / token)
        except OSError:
            raise KernelBusy() from None
        return token

    def restore(self, token: str) -> None:
        source = self._trash_path(token)
        target = self.root / token[33:]
        if (
            target.exists()
            or target.is_symlink()
            or not source.is_dir()
            or source.is_symlink()
        ):
            raise KernelPathInvalid()
        self._validate_tree(source)
        source.rename(target)

    def purge(self, token: str) -> None:
        target = self._trash_path(token)
        if target.is_symlink():
            raise KernelPathInvalid()
        if target.exists():
            shutil.rmtree(target)

    def retry_pending(self) -> None:
        self._ensure_roots()
        for item in self.trash.iterdir():
            if not _TOKEN.fullmatch(item.name) or item.is_symlink():
                continue
            target = self.root / item.name[33:]
            if target.exists() or target.is_symlink():
                logger.warning(
                    "kernel recovery conflict preserved for token=%s", item.name
                )
                continue
            try:
                self._validate_install(item)
                item.rename(target)
            except (OSError, KernelPathInvalid):
                logger.warning(
                    "kernel recovery remains pending for token=%s", item.name
                )

    def _kernel_path(self, kernel: KernelRef) -> Path:
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3,4}", kernel.version):
            raise KernelPathInvalid()
        suffix = "-pro" if kernel.edition == "licensed" else ""
        target = self.root / f"chromium-{kernel.version}{suffix}"
        if target.parent != self.root:
            raise KernelPathInvalid()
        return target

    def _trash_path(self, token: str) -> Path:
        self._ensure_roots()
        if not _TOKEN.fullmatch(token):
            raise KernelPathInvalid()
        target = self.trash / token
        if target.parent != self.trash:
            raise KernelPathInvalid()
        return target

    def _ensure_roots(self) -> None:
        if self.root.is_symlink() or self.trash.is_symlink():
            raise KernelPathInvalid()

    @staticmethod
    def _validate_tree(root: Path) -> None:
        if not root.is_dir() or root.is_symlink():
            raise KernelPathInvalid()
        resolved_root = root.resolve()
        try:
            for item in root.rglob("*"):
                if item.is_symlink():
                    item.resolve().relative_to(resolved_root)
        except (OSError, ValueError):
            raise KernelPathInvalid() from None

    def _validate_install(self, root: Path) -> None:
        self._validate_tree(root)
        if not executable_path(root, self.platform).is_file():
            raise KernelPathInvalid()


def kernel_target_lock(root: Path, edition: str, version: str) -> ExclusiveFileLock:
    if edition not in {"public", "licensed"} or not is_valid_kernel_version(version):
        raise KernelPathInvalid()
    suffix = "-pro" if edition == "licensed" else ""
    return ExclusiveFileLock(
        root / ".install-targets" / f"chromium-{version}{suffix}.lock"
    )
