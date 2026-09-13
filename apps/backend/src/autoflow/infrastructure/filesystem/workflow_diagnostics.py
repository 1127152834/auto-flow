"""Registered diagnostic reads and bounded-memory result archive generation."""
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


def read_workflow_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def result_archive(items: list[tuple[Path, dict[str, Any]]]) -> Iterator[bytes]:
    with TemporaryFile() as stream:
        with ZipFile(stream, 'w', ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr('manifest.json', json.dumps([item for _, item in items], ensure_ascii=False))
            for path, item in items:
                archive.write(path, item['name'])
        stream.seek(0)
        while chunk := stream.read(65536):
            yield chunk
