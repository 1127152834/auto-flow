from __future__ import annotations

import asyncio
import io
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import BinaryOutputSnapshot, ExecutionContext
from PIL import Image


class Artifacts:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    async def read_binary_output(
        self, *, output_path: str, max_bytes: int
    ) -> BinaryOutputSnapshot:
        content = self.files.get(output_path)
        assert content is None or len(content) <= max_bytes
        return BinaryOutputSnapshot(content, "fixture" if content else "missing")


def _image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (20, 10), "white").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.asyncio
async def test_image_ocr_file_uses_bundled_reader_and_preserves_reading_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autoflow.application.workflows.executors import media_recognition

    monkeypatch.setattr(media_recognition, "_easyocr_reader", None)
    calls: list[tuple[object, ...]] = []

    class Reader:
        def __init__(self, languages: list[str], **options: object) -> None:
            calls.append((languages, options))

        def readtext(self, image: np.ndarray):
            assert image.shape == (10, 20, 3)
            return [
                ([[10, 20]], "第二行", 0.9),
                ([[10, 2]], "第一行", 0.9),
            ]

    monkeypatch.setitem(sys.modules, "easyocr", SimpleNamespace(Reader=Reader))
    context = ExecutionContext(
        artifacts=Artifacts({"input.png": _image_bytes()}),
    )

    result = (
        await build_production_executor_registry()
        .get("image_ocr")
        .execute(
            {
                "ocrMode": "file",
                "ocrType": "general",
                "imagePath": "input.png",
                "resultVariable": "text",
            },
            context,
        )
    )

    assert result.success is True
    assert result.data == {"text": "第一行\n第二行", "length": 7}
    assert context.variables["text"] == "第一行\n第二行"
    assert calls[0][0] == ["ch_sim", "en"]
    assert calls[0][1]["download_enabled"] is False


@pytest.mark.asyncio
async def test_image_ocr_captcha_uses_existing_ddddocr_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OCR:
        def classification(self, image: bytes) -> str:
            assert image.startswith(b"\x89PNG")
            return "A7中9"

    monkeypatch.setitem(sys.modules, "ddddocr", SimpleNamespace(DdddOcr=OCR))
    context = ExecutionContext(artifacts=Artifacts({"captcha.png": _image_bytes()}))

    result = (
        await build_production_executor_registry()
        .get("image_ocr")
        .execute(
            {
                "ocrMode": "file",
                "ocrType": "captcha",
                "imagePath": "captcha.png",
                "resultVariable": "text",
            },
            context,
        )
    )

    assert result.success is True
    assert context.variables["text"] == "A7中9"


@pytest.mark.asyncio
async def test_face_recognition_preserves_match_branch_and_result_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[bytes] = []

    def load_image_file(stream: io.BytesIO) -> np.ndarray:
        loaded.append(stream.read())
        return np.zeros((1, 1, 3))

    monkeypatch.setitem(
        sys.modules,
        "face_recognition",
        SimpleNamespace(
            load_image_file=load_image_file,
            face_encodings=lambda _image: [np.array([0.1, 0.2])],
            compare_faces=lambda _known, _target, tolerance: [tolerance == 0.5],
            face_distance=lambda _known, _target: np.array([0.25]),
        ),
    )
    context = ExecutionContext(
        artifacts=Artifacts({"source.png": b"source", "target.png": b"target"})
    )

    result = (
        await build_production_executor_registry()
        .get("face_recognition")
        .execute(
            {
                "sourceImage": "source.png",
                "targetImage": "target.png",
                "tolerance": 0.5,
                "resultVariable": "match",
            },
            context,
        )
    )

    assert result.success is True
    assert result.branch == "true"
    assert result.data == {
        "matched": True,
        "confidence": 75.0,
        "source_faces": 1,
        "target_faces": 1,
        "best_distance": 0.25,
    }
    assert context.variables["match"] == result.data
    assert loaded == [b"source", b"target"]


@pytest.mark.asyncio
async def test_face_recognition_reports_missing_source_before_loading_engine() -> None:
    result = (
        await build_production_executor_registry()
        .get("face_recognition")
        .execute(
            {"sourceImage": "missing.png", "targetImage": "target.png"},
            ExecutionContext(artifacts=Artifacts({"target.png": b"target"})),
        )
    )

    assert result.success is False
    assert result.error == "识别图片不存在: missing.png"


@pytest.mark.asyncio
async def test_image_ocr_region_normalizes_coordinates_and_returns_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autoflow.application.workflows.executors import media_recognition
    from PIL import ImageGrab

    boxes: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(
        ImageGrab,
        "grab",
        lambda *, bbox: (boxes.append(bbox), Image.new("RGB", (20, 10), "white"))[1],
    )
    monkeypatch.setattr(
        media_recognition, "_recognize_image", lambda _image, _kind: "文字"
    )
    context = ExecutionContext()

    result = (
        await build_production_executor_registry()
        .get("image_ocr")
        .execute(
            {
                "ocrMode": "region",
                "startX": "20",
                "startY": "10",
                "endX": "0",
                "endY": "0",
                "resultVariable": "text",
            },
            context,
        )
    )

    assert result.success is True
    assert boxes == [(0, 0, 20, 10)]
    assert result.data["region"] == {"x1": 0, "y1": 0, "x2": 20, "y2": 10}
    assert context.variables["text"] == "文字"


@pytest.mark.asyncio
async def test_image_ocr_stop_interrupts_before_cpu_recognition() -> None:
    class Cancelled:
        cancelled = True

        def raise_if_cancelled(self) -> None:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await (
            build_production_executor_registry()
            .get("image_ocr")
            .execute(
                {"imagePath": "input.png"},
                ExecutionContext(
                    artifacts=Artifacts({"input.png": _image_bytes()}),
                    cancellation=Cancelled(),
                ),
            )
        )


@pytest.mark.parametrize("module_type", ["face_recognition", "image_ocr"])
def test_media_recognition_family_is_registered_without_browser(
    module_type: str,
) -> None:
    executor = build_production_executor_registry().get(module_type)
    assert executor.requires_browser_for({}) is False


def test_easyocr_default_models_are_owned_resources_not_reference(monkeypatch):
    from pathlib import Path

    from autoflow.application.workflows.executors import media_recognition

    monkeypatch.delenv("AUTOFLOW_EASYOCR_MODEL_DIR", raising=False)
    models = media_recognition._easyocr_model_dir()
    assert models == Path(media_recognition.__file__).resolve().parents[3] / "resources/easyocr"
    assert all((models / name).is_file() for name in ("craft_mlt_25k.pth", "zh_sim_g2.pth"))


def test_missing_bundled_models_never_search_reference(monkeypatch, tmp_path):
    from autoflow.application.workflows.executors import media_recognition

    reference = tmp_path / "reference/WebRPA/backend/models/ocr/easyocr"
    reference.mkdir(parents=True)
    module = tmp_path / "src/autoflow/application/workflows/executors/media_recognition.py"
    module.parent.mkdir(parents=True)
    monkeypatch.setattr(media_recognition, "__file__", str(module))
    monkeypatch.delenv("AUTOFLOW_EASYOCR_MODEL_DIR", raising=False)
    with pytest.raises(RuntimeError, match="模型资源不存在"):
        media_recognition._easyocr_model_dir()
