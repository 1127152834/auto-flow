import os
import re
import shutil
from pathlib import Path, PurePosixPath

_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,80}$")


def validate_archive_path(path: PurePosixPath, entry_type: str = "file") -> None:
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("archive entry escapes its root")
    if entry_type in {"char", "block", "fifo", "device", "link", "symlink", "hardlink"}:
        raise ValueError("special archive entries are not supported")


class BackupStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.staging = self.root / "staging"
        self.final = self.root / "final"

    def _path(self, directory: Path, identifier: str) -> Path:
        if not _SAFE_ID.fullmatch(identifier):
            raise ValueError("invalid backup storage identifier")
        path = (directory / identifier).resolve()
        if path.parent != directory.resolve():
            raise ValueError("backup storage path escapes its root")
        return path

    def stage(self, identifier: str) -> Path:
        self.staging.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(self.staging, identifier)
        path.mkdir(mode=0o700, exist_ok=False)
        return path

    def finalize(self, identifier: str) -> Path:
        self.final.mkdir(mode=0o700, parents=True, exist_ok=True)
        source = self._path(self.staging, identifier)
        target = self._path(self.final, identifier)
        if not source.exists() or target.exists():
            raise FileExistsError(identifier)
        os.replace(source, target)
        return target

    def discard(self, identifier: str) -> None:
        source = self._path(self.staging, identifier)
        if source.exists():
            shutil.rmtree(source)
