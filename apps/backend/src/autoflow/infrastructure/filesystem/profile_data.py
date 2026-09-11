import logging
import re
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from autoflow.domain.profiles.errors import ProfileDataPathInvalid, ProfileDirectoryBusy

logger = logging.getLogger(__name__)
_TOKEN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[0-9a-f]{32}"
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

    def retry_pending(self) -> None:
        self._ensure_roots()
        for entry in self.trash.iterdir():
            if not _TOKEN.fullmatch(entry.name):
                continue
            try:
                self.purge(entry.name)
            except (OSError, ProfileDataPathInvalid):
                logger.warning("profile data cleanup remains pending for token=%s", entry.name)

    def _profile_path(self, profile_id: str) -> Path:
        self._ensure_roots()
        try:
            if str(UUID(profile_id)) != profile_id:
                raise ValueError
        except (ValueError, AttributeError):
            raise ProfileDataPathInvalid from None
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
