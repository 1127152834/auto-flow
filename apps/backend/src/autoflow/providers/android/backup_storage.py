import os
import re
import shutil
import tarfile
from collections import deque
from pathlib import Path, PurePosixPath

_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,80}$")


def validate_archive_path(path: PurePosixPath, entry_type: str = "file") -> None:
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("archive entry escapes its root")
    if entry_type not in {"file", "directory"}:
        raise ValueError("special archive entries are not supported")


def validate_archive_members(members: list[tarfile.TarInfo]) -> None:
    """Validate the whole graph before Docker can extract any member."""
    entries: dict[str, tarfile.TarInfo] = {}
    for member in members:
        path = PurePosixPath(member.name)
        validate_archive_path(path)
        if (
            not path.parts or path.parts[0] != "data"
            or member.name.rstrip("/") != str(path)
            or str(path) in entries
            or (str(path) == "data" and not member.isdir())
            or member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE, tarfile.SYMTYPE, tarfile.LNKTYPE}
            or member.sparse is not None
        ):
            raise ValueError("unsupported or ambiguous archive member")
        if member.islnk():
            # Docker extracts in archive order. Hard links must refer to an
            # already materialized regular file, never a directory or symlink.
            target = entries.get(member.linkname)
            if target is None or not target.isreg():
                raise ValueError("hard link target is not a preceding regular file")
        entries[str(path)] = member

    for name, member in entries.items():
        for parent in PurePosixPath(name).parents:
            ancestor = entries.get(str(parent))
            if ancestor is not None and not ancestor.isdir():
                raise ValueError("archive would write through a non-directory")
        if not member.issym():
            continue
        if not member.linkname or "\0" in member.linkname:
            raise ValueError("invalid symbolic link target")
        # Resolve components in filesystem order: normalize '..' only after
        # expanding intervening links, otherwise chained links can escape /data.
        parts: list[str] = []
        pending = deque(name.split("/"))
        hops = 0
        while pending:
            part = pending.popleft()
            if part in {"", "."}:
                continue
            if part == "..":
                if len(parts) <= 1:
                    raise ValueError("link escapes data root")
                parts.pop()
                continue
            parts.append(part)
            if parts[0] != "data":
                raise ValueError("link escapes data root")
            target = entries.get("/".join(parts))
            if target is not None and target.issym():
                hops += 1
                if hops > 40 or not target.linkname:
                    raise ValueError("cyclic or excessive symbolic link chain")
                parts.pop()
                if target.linkname.startswith("/"):
                    parts.clear()
                pending.extendleft(reversed(target.linkname.split("/")))
            elif pending and target is not None and not target.isdir():
                raise ValueError("link traverses a non-directory")
        if not parts or parts[0] != "data":
            raise ValueError("link escapes data root")


class BackupStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.absolute()
        self.staging = self.root / "staging"
        self.final = self.root / "final"

    def _path(self, directory: Path, identifier: str) -> Path:
        if not _SAFE_ID.fullmatch(identifier):
            raise ValueError("invalid backup storage identifier")
        self._directory(self.root)
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
        path = self._path(self.staging, identifier)
        path.mkdir(mode=0o700, exist_ok=False)
        os.chmod(path, 0o700)
        return path

    def finalize(self, identifier: str) -> Path:
        source = self._path(self.staging, identifier)
        target = self._path(self.final, identifier)
        if not source.is_dir() or source.is_symlink() or target.exists() or target.is_symlink():
            raise FileExistsError(identifier)
        for entry in source.iterdir():
            if entry.is_symlink() or not entry.is_file():
                raise ValueError("backup staging contains an unsupported entry")
            os.chmod(entry, 0o600)
            self._sync(entry)
        self._sync(source)
        os.replace(source, target)
        try:
            for directory in (self.staging, self.final, self.root, self.root.parent):
                self._sync(directory)
        except BaseException:
            # This call created target; never remove a pre-existing backup.
            shutil.rmtree(target)
            self._sync(self.final)
            raise
        return target

    @staticmethod
    def _sync(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

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
