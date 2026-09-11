import logging
import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from autoflow.domain.kernels.errors import KernelBusy, KernelNotFound, KernelPathInvalid
from autoflow.domain.kernels.models import KernelRef
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock

logger = logging.getLogger(__name__)
_TOKEN = re.compile(r"[0-9a-f]{32}-chromium-[0-9]+(?:\.[0-9]+){3,4}(?:-pro)?")


class FilesystemKernelInstallationStore:
    def __init__(self, root: Path) -> None:
        absolute = Path(root).absolute()
        if absolute.is_symlink():
            raise KernelPathInvalid()
        absolute.mkdir(parents=True, exist_ok=True)
        self.root = absolute.resolve()
        self.trash = self.root / ".trash"
        if self.trash.is_symlink():
            raise KernelPathInvalid()
        self.trash.mkdir(exist_ok=True)

    @contextmanager
    def guard(self) -> Iterator[None]:
        self._ensure_roots()
        lock = ExclusiveFileLock(self.root / ".install.lock")
        try:
            if not lock.acquire():
                raise KernelBusy()
        except OSError:
            raise KernelBusy() from None
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
        if target.exists() or target.is_symlink() or not source.is_dir() or source.is_symlink():
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
                logger.warning("kernel recovery conflict preserved for token=%s", item.name)
                continue
            try:
                self._validate_tree(item)
                item.rename(target)
            except (OSError, KernelPathInvalid):
                logger.warning("kernel recovery remains pending for token=%s", item.name)

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
