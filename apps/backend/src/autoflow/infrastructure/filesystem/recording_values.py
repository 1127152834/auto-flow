import json
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID

from .workflow_artifacts import WorkflowArtifacts, artifact_path


class RecordingValues:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def write(self, identifier: str, value: Any) -> str:
        return str(WorkflowArtifacts(self.root, str(UUID(identifier))).save_json('recording', value)['relativePath'])

    def read(self, identifier: str, reference: str) -> Any:
        return json.loads(artifact_path(self.root, str(UUID(identifier)), reference).read_text())

    def remove(self, identifier: str) -> None:
        path = self.root.resolve() / str(UUID(identifier))
        if path.is_symlink() or path.resolve().parent != self.root.resolve():
            raise ValueError('Invalid recording directory')
        if path.exists():
            shutil.rmtree(path)
