from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from PIL import Image

from autoflow.application.workflows.executors import media_recognition
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import BinaryOutputSnapshot, ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_media_recognition_harness.py")


class _Artifacts:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    async def read_binary_output(
        self, *, output_path: str, max_bytes: int
    ) -> BinaryOutputSnapshot:
        content = self.files[output_path]
        assert len(content) <= max_bytes
        return BinaryOutputSnapshot(content, "fixture")


class _Reader:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def readtext(self, _image: np.ndarray):
        return [
            ([[10, 20]], "第二行", 0.9),
            ([[10, 2]], "第一行", 0.9),
        ]


def _image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (20, 10), "white").save(output, format="PNG")
    return output.getvalue()


def _source_result(payload: dict[str, Any]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize("module_type", ["face_recognition", "image_ocr"])
def test_media_recognition_output_matches_frozen_source(
    module_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = _image_bytes()
    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=_Reader))
    monkeypatch.setitem(
        sys.modules,
        "face_recognition",
        SimpleNamespace(
            load_image_file=lambda stream: (stream.read(), np.zeros((1, 1, 3)))[1],
            face_encodings=lambda _image: [np.array([0.1, 0.2])],
            compare_faces=lambda _known, _target, tolerance: [tolerance == 0.5],
            face_distance=lambda _known, _target: np.array([0.25]),
        ),
    )
    monkeypatch.setattr(media_recognition, "_easyocr_reader", None)
    config = (
        {"tolerance": 0.5, "resultVariable": "out"}
        if module_type == "face_recognition"
        else {
            "ocrMode": "file",
            "ocrType": "general",
            "resultVariable": "out",
        }
    )
    source = _source_result(
        {
            "type": module_type,
            "config": config,
            "files": [base64.b64encode(image).decode()] * 2,
        }
    )
    paths = (
        {"source.png": image, "target.png": image}
        if module_type == "face_recognition"
        else {"input.png": image}
    )
    target_config = {
        **config,
        **(
            {"sourceImage": "source.png", "targetImage": "target.png"}
            if module_type == "face_recognition"
            else {"imagePath": "input.png"}
        ),
    }
    context = ExecutionContext(artifacts=_Artifacts(paths))
    result = asyncio.run(
        build_production_executor_registry()
        .get(module_type)
        .execute(target_config, context)
    )
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "branch": result.branch,
        "variables": context.variables,
    }

    assert target == source
