from pathlib import Path

import pytest

from autoflow.application.android.backups import AndroidBackupService
from autoflow.domain.android.ports import AndroidError


def test_backup_requires_stopped_unowned_device_and_uses_workspace_path(tmp_path: Path):
    service = AndroidBackupService(_Resources(), tmp_path)
    with pytest.raises(AndroidError):
        service.create({"deviceId": "d", "name": "x"}, {"androidStatus": "ready", "control": "idle"})


class _Resources:
    def __init__(self): self.items = {}
    def save(self, kind, item): self.items[(kind, item["id"])] = item
    def list(self, kind): return [item for (stored, _), item in self.items.items() if stored == kind]
