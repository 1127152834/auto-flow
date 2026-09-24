import io
import tarfile

import pytest

from autoflow.application.android.backups import AndroidBackupService
from autoflow.domain.android.ports import AndroidError


def archive_bytes(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, kind, target in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.uid, member.gid, member.mode = 10001, 10002, 0o750
            member.linkname = target
            archive.addfile(member)
    return stream.getvalue()


@pytest.mark.parametrize("target", ["file", "../dir/file", "/data/dir/file", "next"])
def test_safe_internal_symlinks_and_hardlinks_are_supported(target):
    data = archive_bytes([
        ("data/dir", tarfile.DIRTYPE, ""),
        ("data/dir/file", tarfile.REGTYPE, ""),
        ("data/dir/next", tarfile.SYMTYPE, "file"),
        ("data/dir/link", tarfile.SYMTYPE, target),
        ("data/hard", tarfile.LNKTYPE, "data/dir/file"),
    ])
    AndroidBackupService._validate_archive(data)


@pytest.mark.parametrize("entries", [
    [("etc/passwd", tarfile.REGTYPE, "")],
    [("data", tarfile.REGTYPE, "")],
    [("data/file", b"V", "")],
    [("data/file", tarfile.FIFOTYPE, "")],
    [("data/file", tarfile.CHRTYPE, "")],
    [("data/file", tarfile.REGTYPE, ""), ("data/file", tarfile.REGTYPE, "")],
    [("data/file", tarfile.REGTYPE, ""), ("data/file/child", tarfile.REGTYPE, "")],
    [("data/link", tarfile.SYMTYPE, "/etc")],
    [("data/link", tarfile.SYMTYPE, "../outside")],
    [("data/link", tarfile.SYMTYPE, "link")],
    [("data/a", tarfile.SYMTYPE, "b"), ("data/b", tarfile.SYMTYPE, "a")],
    [("data/link", tarfile.SYMTYPE, "dir"), ("data/link/child", tarfile.REGTYPE, "")],
    [("data/link/child", tarfile.REGTYPE, ""), ("data/link", tarfile.SYMTYPE, "dir")],
    [("data/hard", tarfile.LNKTYPE, "data/missing")],
    [("data/dir", tarfile.DIRTYPE, ""), ("data/hard", tarfile.LNKTYPE, "data/dir")],
    [("data/hard", tarfile.LNKTYPE, "/data/file"), ("data/file", tarfile.REGTYPE, "")],
    [("data/a", tarfile.SYMTYPE, "/data"), ("data/b", tarfile.SYMTYPE, "a/../outside")],
])
def test_unsafe_or_ambiguous_entries_are_rejected(entries):
    with pytest.raises(AndroidError) as error:
        AndroidBackupService._validate_archive(archive_bytes(entries))
    assert error.value.code == "ANDROID_BACKUP_INCOMPATIBLE"


def test_guest_tar_xattrs_and_acls_are_valid_archive_metadata():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        root = tarfile.TarInfo("data")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        member = tarfile.TarInfo("data/file")
        member.pax_headers = {"SCHILY.xattr.user.autoflow_probe": "metadata", "SCHILY.acl.access": "user::rw-\ngroup::r--\nother::---\n"}
        archive.addfile(member)
    AndroidBackupService._validate_archive(stream.getvalue())
