import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
from collections import deque
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock

_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,80}$")


def _identity(info: os.stat_result) -> tuple[int, ...]:
    # Reading changes atime on some filesystems; it is not a content revision.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


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
            # Tar extracts in archive order. Hard links must refer to an
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

    def require_space(self, archive_bytes: int, manifest_bytes: int) -> None:
        if type(archive_bytes) is not int or archive_bytes <= 0:
            raise AndroidError("ANDROID_DISK_ESTIMATE_UNKNOWN", "无法估计备份所需空间，归档尚未写入", 409)
        target = self.staging
        while not target.exists():
            target = target.parent
        try:
            free = shutil.disk_usage(target).free
            block = os.statvfs(target).f_frsize
            if type(free) is not int or free < 0 or type(block) is not int or block <= 0:
                raise ValueError("invalid filesystem capacity")
        except (OSError, ValueError) as error:
            raise AndroidError("ANDROID_DISK_PROBE_FAILED", "无法核实备份目录可用空间，归档尚未写入", 409) from error
        # ponytail: one block per new directory is an estimate; retain ENOSPC cleanup for metadata growth and external writers.
        directory_blocks = 1 + sum(not path.exists() for path in (self.root, self.staging, self.final))
        required = sum((size + block - 1) // block * block for size in (archive_bytes, manifest_bytes)) + block * directory_blocks
        if free < required:
            raise AndroidError("ANDROID_DISK_SPACE_INSUFFICIENT", f"备份目录空间不足：预计需要 {required} 字节，可用 {free} 字节", 409)

    @contextmanager
    def lock(self):
        lock = ExclusiveFileLock(self.root.parent / "android-backups.lock")
        if not lock.acquire():
            raise AndroidError("ANDROID_BACKUP_BUSY", "备份、恢复或数据清理正在使用文件，请稍后再试", 409)
        try:
            yield
        finally:
            lock.release()

    def snapshot(self, directory: Path) -> dict[str, int | str]:
        if (
            self.root.is_symlink() or directory.parent not in {self.staging, self.final}
            or directory.parent.is_symlink() or directory.is_symlink()
            or not directory.is_dir() or not _SAFE_ID.fullmatch(directory.name)
        ):
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理路径已变化或不在受控目录内", 409)
        before = directory.stat()
        # ponytail: explicit cleanup scans hash file contents; cache by inode/ctime if large archives make previews slow.
        digest, size = hashlib.sha256(), 0
        for child in sorted(directory.iterdir()):
            info = child.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理目录包含不支持的链接或特殊条目", 409)
            descriptor = os.open(child, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                if _identity(os.fstat(stream.fileno())) != _identity(info) or _identity(child.lstat()) != _identity(info):
                    raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理文件正在变化，请重新预览", 409)
            size += info.st_size
            digest.update(json.dumps([child.name, *_identity(info)]).encode())
        after = directory.stat()
        if _identity(before) != _identity(after):
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理目录正在变化，请重新预览", 409)
        digest.update(json.dumps(_identity(before)).encode())
        return {"size": size, "filesystemFingerprint": digest.hexdigest()}

    def inventory(self, registered_ids: set[str]) -> list[dict]:
        if self.root.is_symlink():
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "备份根目录不是受控目录", 409)
        items = []
        for parent, prefix in ((self.staging, "staging"), (self.final, "orphan")):
            if parent.is_symlink():
                raise AndroidError("ANDROID_CLEANUP_CHANGED", "备份目录不是受控目录", 409)
            if not parent.is_dir():
                continue
            for candidate in sorted(parent.iterdir()):
                if candidate.is_symlink() or not candidate.is_dir() or not _SAFE_ID.fullmatch(candidate.name):
                    continue
                if prefix == "orphan" and candidate.name in registered_ids:
                    continue
                snapshot = self.snapshot(candidate)
                try:
                    descriptor = os.open(candidate / "manifest.json", os.O_RDONLY | os.O_NOFOLLOW)
                    with os.fdopen(descriptor, "rb") as stream:
                        content = stream.read(65537)
                    manifest = json.loads(content) if len(content) <= 65536 else {}
                except (OSError, ValueError):
                    manifest = {}
                references = []
                if isinstance(manifest, dict) and manifest.get("formatVersion") == 1:
                    for field, kind in (("deviceId", "device"), ("imageId", "image")):
                        value = manifest.get(field)
                        if isinstance(value, str) and 0 < len(value) <= 256:
                            references.append({"kind": kind, "id": value})
                items.append({"id": prefix + ":" + candidate.name, "kind": "backup-" + prefix,
                              "purpose": "backup-staging" if prefix == "staging" else "unregistered-backup",
                              "references": references or [{"kind": "unknown", "id": "source", "name": "来源未核实"}],
                              "path": str(candidate), **snapshot})
        return items

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
