"""Run-owned files; public reads additionally require a registered artifact ID."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def _segment(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("Invalid artifact path")
    return value


def artifact_path(runs_root: Path, run_id: str, relative_path: str) -> Path:
    expected = runs_root.resolve(strict=True) / _segment(run_id) / "artifacts"
    root = expected.resolve(strict=True)
    if root != expected:
        raise ValueError("Invalid artifact path")
    # A registry entry is always one filename, never an arbitrary outputPath.
    path = root / _segment(relative_path)
    resolved = path.resolve(strict=True)
    if path.is_symlink() or resolved.parent != root or not resolved.is_file():
        raise ValueError("Invalid artifact path")
    if not root.is_relative_to(runs_root.resolve(strict=True)):
        raise ValueError("Invalid artifact path")
    return resolved


class WorkflowArtifacts:
    def __init__(self, runs_root: Path, run_id: str) -> None:
        self.root = runs_root.resolve() / _segment(run_id) / "artifacts"
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.resolve() != self.root:
            raise ValueError("Invalid artifact directory")

    def save_json(self, node_id: str, value: Any) -> dict[str, Any]:
        artifact_id = uuid4().hex
        name = f"{artifact_id}.json"
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        self._write(self.root / name, text.encode("utf-8"))
        return self._record(artifact_id, node_id, "json", name, None, text[:240])

    def save_png(self, node_id: str, data: bytes, save_path: str) -> dict[str, Any]:
        artifact_id = uuid4().hex
        name = f"{artifact_id}.png"
        canonical = self.root / name
        target = self._image_target(save_path, name)
        self._write(target, data)
        if target != canonical:
            try:
                self._write(canonical, data)
            except BaseException:
                # This call owns the target exclusively, so rollback cannot delete a user's file.
                target.unlink(missing_ok=True)
                raise
        return self._record(artifact_id, node_id, "image", name, str(target), str(target)[:240])

    def _image_target(self, value: str, generated_name: str) -> Path:
        requested = Path(value) if value else self.root
        relative = bool(value) and not requested.is_absolute()
        if relative:
            requested = self.root / requested
        # Resolve parent components, but never follow an existing final filename symlink.
        target = requested if requested.suffix.lower() == ".png" else requested / generated_name
        target = target.parent.resolve() / target.name
        if relative and not target.is_relative_to(self.root.resolve()):
            raise ValueError("Screenshot path escapes this run's artifact directory")
        if target.exists() or target.is_symlink():
            raise FileExistsError("Screenshot file already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative and not target.parent.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Screenshot path escapes this run's artifact directory")
        return target

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        # Exclusive creation also refuses final symlinks and races with another writer.
        with path.open("xb") as stream:
            try:
                stream.write(data)
                stream.flush()
            except BaseException:
                path.unlink(missing_ok=True)
                raise

    @staticmethod
    def _record(
        artifact_id: str, node_id: str, kind: str, name: str,
        output_path: str | None, preview: str,
    ) -> dict[str, Any]:
        return {
            "id": artifact_id, "nodeId": node_id, "kind": kind, "name": name,
            "mimeType": "image/png" if kind == "image" else "application/json",
            "relativePath": name, "outputPath": output_path, "preview": preview,
        }
