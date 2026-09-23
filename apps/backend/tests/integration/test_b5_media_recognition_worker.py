from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from skimage import data

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


def _write_fixtures(root: Path) -> tuple[Path, Path]:
    face = root / "face.png"
    Image.fromarray(data.astronaut()).save(face)
    font_paths = (
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    font_path = next((path for path in font_paths if path.exists()), None)
    if font_path is None:
        pytest.skip("没有可用于真实OCR夹具的系统字体")
    text = root / "text.png"
    image = Image.new("RGB", (800, 180), "white")
    ImageDraw.Draw(image).text(
        (20, 30),
        "AUTOFLOW 123",
        fill="black",
        font=ImageFont.truetype(str(font_path), 96),
    )
    image.save(text)
    return face, text


async def _run(
    manager: WorkflowWorkerManager,
    events: list[dict[str, object]],
    *,
    run_id: str,
    module_type: str,
    config: dict[str, object],
    artifact_root: Path,
) -> dict[str, object]:
    start = len(events)
    await manager.start(
        run_id,
        "profile-1",
        None,
        {
            "runId": run_id,
            "workflowId": "media-recognition-flow",
            "profileId": "profile-1",
            "requiresBrowser": False,
            "artifactRoot": str(artifact_root),
            "document": {
                "nodes": [
                    {
                        "id": "recognize",
                        "type": "moduleNode",
                        "data": {"moduleType": module_type, "config": config},
                    }
                ],
                "edges": [],
                "variables": [],
            },
        },
    )
    for _ in range(12_000):
        if not manager.busy():
            break
        await asyncio.sleep(0.01)
    completed = [
        event
        for event in events[start:]
        if event.get("type") == "execution:node_complete"
    ]
    assert manager.busy() is False
    assert len(completed) == 1
    return completed[0]


@pytest.mark.asyncio
async def test_real_worker_runs_face_recognition_and_easyocr(tmp_path: Path) -> None:
    face, text = _write_fixtures(tmp_path)
    events: list[dict[str, object]] = []
    artifact_root = tmp_path / "artifacts"
    frozen_backend = os.environ.get("AUTOFLOW_FROZEN_BACKEND")
    command = (frozen_backend, "--workflow-worker") if frozen_backend else None
    manager = WorkflowWorkerManager(
        tmp_path,
        command=command,
        termination_timeout=1,
        on_event=lambda event: events.append(event),
    )
    try:
        face_event = await _run(
            manager,
            events,
            run_id="face-recognition-run",
            module_type="face_recognition",
            config={
                "sourceImage": str(face),
                "targetImage": str(face),
                "resultVariable": "face_result",
            },
            artifact_root=artifact_root,
        )
        assert face_event.get("success") is True
        assert face_event.get("data", {}).get("matched") is True

        ocr_event = await _run(
            manager,
            events,
            run_id="image-ocr-run",
            module_type="image_ocr",
            config={
                "ocrMode": "file",
                "ocrType": "general",
                "imagePath": str(text),
                "resultVariable": "ocr_text",
            },
            artifact_root=artifact_root,
        )
        assert ocr_event.get("success") is True, ocr_event
        assert "AUTOFLOW" in str(ocr_event.get("message"))
        assert "123" in str(ocr_event.get("message"))
    finally:
        await manager.shutdown()
