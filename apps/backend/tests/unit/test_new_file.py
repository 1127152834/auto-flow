import ctypes
from types import SimpleNamespace

import pytest

from autoflow.infrastructure.filesystem import new_file


@pytest.mark.parametrize("succeeds", [True, False])
def test_windows_publication_uses_write_through_without_replace(tmp_path, monkeypatch, succeeds):
    calls = []

    def move(source, target, flags):
        calls.append((source, target, flags))
        return succeeds

    monkeypatch.setattr(new_file, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: SimpleNamespace(MoveFileExW=move), raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 183, raising=False)
    monkeypatch.setattr(ctypes, "WinError", lambda _code: FileExistsError("existing file"), raising=False)
    temporary, target = tmp_path / "temporary", tmp_path / "target"
    target.write_bytes(b"keep")
    if succeeds:
        new_file.publish_new_file(temporary, target)
    else:
        with pytest.raises(FileExistsError):
            new_file.publish_new_file(temporary, target)
    assert calls == [(str(temporary), str(target), 8)]
    assert target.read_bytes() == b"keep"
