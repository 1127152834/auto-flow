"""Temporary Playwright archive staging; never publish an unfinished ZIP."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from autoflow.domain.workflows.runs import WorkflowArtifact, WorkflowRunError


class TraceArchive:
    def __init__(self) -> None:
        self._directory = TemporaryDirectory(prefix="autoflow-trace-")
        self.path = Path(self._directory.name) / "trace.zip"

    def read(self, limit: int) -> bytes:
        with self.path.open("rb") as stream:
            content = stream.read(limit + 1)
        if len(content) > limit:
            raise ValueError("追踪归档超过本次 64 MiB 读取上限")
        return content

    def close(self) -> None:
        self._directory.cleanup()


def read_trace_manifest(root: Path, artifact: WorkflowArtifact) -> dict[str, Any]:
    """Only read an intact registered index; never unpack or execute trace resources."""
    import hashlib
    import json

    path = (root / artifact.relative_path).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise WorkflowRunError('TRACE_FILE_MISSING', 'Trace 索引文件缺失', 404)
    try:
        with path.open('rb') as stream:
            content = stream.read(16 * 1024 * 1024 + 1)
        if len(content) > 16 * 1024 * 1024 or len(content) != artifact.size or hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise ValueError('Trace index integrity mismatch')
        value = json.loads(content)
        if not isinstance(value, dict) or value.get('schemaVersion') != 1 or not isinstance(value.get('events'), list):
            raise ValueError('Unsupported Trace index')
        return value
    except (OSError, ValueError) as error:
        raise WorkflowRunError('TRACE_INDEX_INVALID', 'Trace 索引损坏或格式不受支持', 422) from error
