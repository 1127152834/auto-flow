import logging
import re
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from autoflow.domain.profiles.errors import ProfileDataPathInvalid, ProfileDirectoryBusy
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock

logger = logging.getLogger(__name__)
_TOKEN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[0-9a-f]{32}"
)
_CHROMIUM_ACTIVITY_MARKERS = (
    "SingletonLock",
    "SingletonSocket",
    "SingletonCookie",
    "DevToolsActivePort",
)


class FilesystemProfileDataStore:
    def __init__(self, profiles_root: Path) -> None:
        root = Path(profiles_root).absolute()
        if root.is_symlink():
            raise ProfileDataPathInvalid
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.trash = self.root / ".trash"
        if self.trash.is_symlink():
            raise ProfileDataPathInvalid
        self.trash.mkdir(exist_ok=True)

    def stage(self, profile_id: str) -> str | None:
        self._ensure_roots()
        source = self._profile_path(profile_id)
        if source.is_symlink():
            raise ProfileDataPathInvalid
        if not source.exists():
            return None
        if not source.is_dir() or any(path.is_symlink() for path in source.rglob("*")):
            raise ProfileDataPathInvalid
        token = f"{profile_id}-{uuid4().hex}"
        try:
            source.rename(self.trash / token)
        except OSError:
            raise ProfileDirectoryBusy from None
        return token

    def restore(self, profile_id: str, token: str) -> None:
        source = self._trash_path(token)
        target = self._profile_path(profile_id)
        if (
            not token.startswith(f"{profile_id}-")
            or source.is_symlink()
            or target.exists()
            or target.is_symlink()
            or not source.is_dir()
        ):
            raise ProfileDataPathInvalid
        source.rename(target)

    def purge(self, token: str) -> None:
        target = self._trash_path(token)
        if target.is_symlink():
            raise ProfileDataPathInvalid
        if target.exists():
            shutil.rmtree(target)

    def retry_pending(self, profile_exists: Callable[[str], bool]) -> None:
        self._ensure_roots()
        for entry in self.trash.iterdir():
            if not _TOKEN.fullmatch(entry.name):
                continue
            profile_id = entry.name[:36]
            if profile_exists(profile_id):
                target = self._profile_path(profile_id)
                if target.exists() or target.is_symlink():
                    logger.warning(
                        "profile data recovery conflict preserved for profile_id=%s", profile_id
                    )
                    continue
                try:
                    self.restore(profile_id, entry.name)
                except (OSError, ProfileDataPathInvalid):
                    logger.warning(
                        "profile data recovery remains pending for profile_id=%s", profile_id
                    )
                continue
            if _has_chromium_activity_marker(entry):
                logger.warning(
                    "profile data cleanup blocked by Chromium activity marker for profile_id=%s",
                    profile_id,
                )
                continue
            try:
                self.purge(entry.name)
            except (OSError, ProfileDataPathInvalid):
                logger.warning("profile data cleanup remains pending for token=%s", entry.name)

    def _profile_path(self, profile_id: str) -> Path:
        self._ensure_roots()
        _validate_profile_id(profile_id)
        path = self.root / profile_id
        if path.parent != self.root:
            raise ProfileDataPathInvalid
        return path

    def _trash_path(self, token: str) -> Path:
        self._ensure_roots()
        if not _TOKEN.fullmatch(token):
            raise ProfileDataPathInvalid
        path = self.trash / token
        if path.parent != self.trash:
            raise ProfileDataPathInvalid
        return path

    def _ensure_roots(self) -> None:
        if self.root.is_symlink() or self.trash.is_symlink():
            raise ProfileDataPathInvalid


class FilesystemProfileUsageGuard:
    """Coordinate AutoFlow users and conservatively reject Chromium activity markers.

    Portable OS locks only cover processes participating in this protocol. An unrelated
    process that opens an arbitrary file without this lock or a Chromium marker cannot be
    detected reliably across Windows and macOS.
    """

    def __init__(self, profiles_root: Path) -> None:
        root = Path(profiles_root).absolute()
        if root.is_symlink():
            raise ProfileDataPathInvalid
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.locks = self.root / ".locks"
        if self.locks.is_symlink():
            raise ProfileDataPathInvalid
        self.locks.mkdir(exist_ok=True)

    @contextmanager
    def guard(self, profile_id: str) -> Iterator[None]:
        _validate_profile_id(profile_id)
        if self.root.is_symlink() or self.locks.is_symlink():
            raise ProfileDataPathInvalid
        lock_path = self.locks / f"{profile_id}.lock"
        if lock_path.is_symlink():
            raise ProfileDataPathInvalid
        lock = ExclusiveFileLock(lock_path)
        try:
            if not lock.acquire():
                raise ProfileDirectoryBusy
        except OSError:
            raise ProfileDirectoryBusy from None
        try:
            profile_path = self.root / profile_id
            if profile_path.is_symlink():
                raise ProfileDataPathInvalid
            if _has_chromium_activity_marker(profile_path):
                raise ProfileDirectoryBusy
            yield
        finally:
            lock.release()


def _validate_profile_id(profile_id: str) -> None:
    try:
        if str(UUID(profile_id)) != profile_id:
            raise ValueError
    except (ValueError, AttributeError):
        raise ProfileDataPathInvalid from None


def _has_chromium_activity_marker(profile_path: Path) -> bool:
    return any(
        (profile_path / marker).exists() or (profile_path / marker).is_symlink()
        for marker in _CHROMIUM_ACTIVITY_MARKERS
    )
