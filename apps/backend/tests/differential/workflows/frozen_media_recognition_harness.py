# mypy: ignore-errors
from __future__ import annotations

import asyncio
import base64
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from app.executors.base import ExecutionContext
from app.executors.media_recognition import FaceRecognitionExecutor, ImageOCRExecutor


class _Reader:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def readtext(self, _image):
        return [
            ([[10, 20]], "第二行", 0.9),
            ([[10, 2]], "第一行", 0.9),
        ]


def _load(stream):
    if isinstance(stream, str):
        Path(stream).read_bytes()
    else:
        stream.read()
    return np.zeros((1, 1, 3))


sys.modules["easyocr"] = SimpleNamespace(Reader=_Reader)
sys.modules["face_recognition"] = SimpleNamespace(
    load_image_file=_load,
    face_encodings=lambda _image: [np.array([0.1, 0.2])],
    compare_faces=lambda _known, _target, tolerance: [tolerance == 0.5],
    face_distance=lambda _known, _target: np.array([0.25]),
)


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        files = []
        for index, encoded in enumerate(payload["files"]):
            path = root / f"input-{index}.png"
            path.write_bytes(base64.b64decode(encoded))
            files.append(str(path))
        config = dict(payload["config"])
        if payload["type"] == "face_recognition":
            config.update(sourceImage=files[0], targetImage=files[1])
            executor = FaceRecognitionExecutor()
        else:
            config["imagePath"] = files[0]
            executor = ImageOCRExecutor()
        context = ExecutionContext()
        result = await executor.execute(config, context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "branch": result.branch,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
