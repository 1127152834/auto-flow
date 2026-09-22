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
        directory = self._directory(directory)
        path = directory / identifier
        resolved = path.resolve()
        if resolved.parent != directory.resolve() or path.is_symlink():
            raise ValueError("backup storage path escapes its root")
        return path

    @staticmethod
    def _directory(directory: Path) -> Path:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("backup storage directory is not a private directory")
        os.chmod(directory, 0o700)
        return directory

    def stage(self, identifier: str) -> Path:
        self._directory(self.staging)
        path = self._path(self.staging, identifier)
        path.mkdir(mode=0o700, exist_ok=False)
        os.chmod(path, 0o700)
        return path

    def finalize(self, identifier: str) -> Path:
        self._directory(self.final)
        source = self._path(self.staging, identifier)
        target = self._path(self.final, identifier)
        if not source.is_dir() or source.is_symlink() or target.exists() or target.is_symlink():
            raise FileExistsError(identifier)
        for entry in source.iterdir():
            if entry.is_symlink() or not entry.is_file():
                raise ValueError("backup staging contains an unsupported entry")
            os.chmod(entry, 0o600)
        os.replace(source, target)
        os.chmod(target, 0o700)
        return target

    def discard(self, identifier: str) -> None:
        source = self._path(self.staging, identifier)
        if source.exists():
            if source.is_symlink():
                source.unlink()
                return
            shutil.rmtree(source)

    def discard_final(self, identifier: str) -> None:
        target = self._path(self.final, identifier)
        if target.exists():
            if target.is_symlink() or not target.is_dir():
                raise ValueError("backup final path is not a private directory")
            shutil.rmtree(target)
