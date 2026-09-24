"""WebRPA image OCR and face recognition executors.

Source: reference/WebRPA/backend/app/executors/media_recognition.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: image files use AutoFlow's guarded artifact reader; bundled model lookup
supports source development and frozen distributions without runtime downloads.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import os
from pathlib import Path
from threading import Lock
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float

MAX_IMAGE_BYTES = 64 * 1024 * 1024
_easyocr_reader: Any = None
_easyocr_lock = Lock()


def _raise_if_cancelled(context: ExecutionContext) -> None:
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()


async def _read_image(context: ExecutionContext, path: str) -> bytes:
    writer = context.node_artifacts
    if writer is None:
        raise RuntimeError("图片文件读取服务未配置")
    snapshot = await writer.read_binary_output(
        output_path=path,
        max_bytes=MAX_IMAGE_BYTES,
    )
    if snapshot.content is None:
        raise FileNotFoundError(path)
    return snapshot.content


def _easyocr_model_dir() -> Path:
    configured = os.environ.get("AUTOFLOW_EASYOCR_MODEL_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    packaged = Path(__file__).resolve().parents[3] / "resources" / "easyocr"
    if packaged.is_dir():
        return packaged
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "reference/WebRPA/backend/models/ocr/easyocr"
        if candidate.is_dir():
            return candidate
    raise RuntimeError("EasyOCR 模型资源不存在")


def _reader() -> Any:
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader
    with _easyocr_lock:
        if _easyocr_reader is None:
            import easyocr  # type: ignore[import-untyped]

            _easyocr_reader = easyocr.Reader(
                ["ch_sim", "en"],
                gpu=False,
                verbose=False,
                model_storage_directory=str(_easyocr_model_dir()),
                download_enabled=False,
            )
    return _easyocr_reader


def _captcha_text(image: Any) -> str:
    import ddddocr  # type: ignore[import-untyped]
    from PIL import ImageEnhance

    gray = image.convert("L")
    enhanced = ImageEnhance.Contrast(gray).enhance(1.5)
    if enhanced.width < 200 or enhanced.height < 50:
        from PIL import Image

        scale = max(200 / enhanced.width, 50 / enhanced.height, 2)
        enhanced = enhanced.resize(
            (int(enhanced.width * scale), int(enhanced.height * scale)),
            Image.Resampling.LANCZOS,
        )
    output = io.BytesIO()
    enhanced.save(output, format="PNG")
    with contextlib.redirect_stdout(io.StringIO()):
        engine = ddddocr.DdddOcr()
    return str(engine.classification(output.getvalue()))


def _general_text(image: Any) -> str:
    import numpy as np  # type: ignore[import-untyped]
    from PIL import Image

    rgb = image.convert("RGB")
    max_side = max(rgb.width, rgb.height)
    if max_side > 1600:
        scale = 1600 / max_side
        rgb = rgb.resize(
            (int(rgb.width * scale), int(rgb.height * scale)),
            Image.Resampling.LANCZOS,
        )
    results = _reader().readtext(np.array(rgb))
    ordered = sorted(results, key=lambda item: (item[0][0][1], item[0][0][0]))
    return "\n".join(str(item[1]) for item in ordered)


def _recognize_image(image: Any, ocr_type: str) -> str:
    return _captcha_text(image) if ocr_type == "captcha" else _general_text(image)


class FaceRecognitionExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "face_recognition"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        source_path = self.get_text(config.get("sourceImage", ""), context)
        target_path = self.get_text(config.get("targetImage", ""), context)
        if not source_path:
            return ModuleResult(success=False, error="识别图片路径不能为空")
        if not target_path:
            return ModuleResult(success=False, error="目标人脸图片路径不能为空")
        tolerance = to_float(config.get("tolerance", 0.6), 0.6, context)
        variable_name = str(config.get("resultVariable", "face_match_result"))
        try:
            try:
                source = await _read_image(context, source_path)
            except FileNotFoundError:
                return ModuleResult(
                    success=False, error=f"识别图片不存在: {source_path}"
                )
            try:
                target = await _read_image(context, target_path)
            except FileNotFoundError:
                return ModuleResult(
                    success=False, error=f"目标人脸图片不存在: {target_path}"
                )
            _raise_if_cancelled(context)
            result = await asyncio.to_thread(self._recognize, source, target, tolerance)
            _raise_if_cancelled(context)
            if variable_name:
                context.set_variable(variable_name, result)
            if "error" in result:
                return ModuleResult(
                    success=True,
                    message=str(result["error"]),
                    data=result,
                    branch="false",
                )
            matched = bool(result["matched"])
            return ModuleResult(
                success=True,
                message=(
                    f"人脸{'匹配' if matched else '不匹配'}，"
                    f"置信度: {result['confidence']}%"
                ),
                data=result,
                branch="true" if matched else "false",
            )
        except ImportError:
            return ModuleResult(success=False, error="人脸识别功能初始化失败")
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"人脸识别失败: {error}")

    @staticmethod
    def _recognize(source: bytes, target: bytes, tolerance: float) -> dict[str, Any]:
        import face_recognition  # type: ignore[import-untyped]

        source_encodings = face_recognition.face_encodings(
            face_recognition.load_image_file(io.BytesIO(source))
        )
        target_encodings = face_recognition.face_encodings(
            face_recognition.load_image_file(io.BytesIO(target))
        )
        if not source_encodings:
            return {
                "matched": False,
                "error": "识别图片中未检测到人脸",
                "source_faces": 0,
                "target_faces": len(target_encodings),
            }
        if not target_encodings:
            return {
                "matched": False,
                "error": "目标图片中未检测到人脸",
                "source_faces": len(source_encodings),
                "target_faces": 0,
            }
        target_encoding = target_encodings[0]
        matches = face_recognition.compare_faces(
            source_encodings, target_encoding, tolerance=tolerance
        )
        distances = face_recognition.face_distance(source_encodings, target_encoding)
        best_index = int(distances.argmin()) if len(distances) else -1
        best_distance = float(distances[best_index]) if best_index >= 0 else 1.0
        return {
            "matched": any(matches),
            "confidence": round((1 - best_distance) * 100, 2),
            "source_faces": len(source_encodings),
            "target_faces": len(target_encodings),
            "best_distance": round(best_distance, 4),
        }


class ImageOCRExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "image_ocr"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        mode = self.get_text(config.get("ocrMode", "file"), context)
        ocr_type = self.get_text(config.get("ocrType", "general"), context)
        variable_name = str(config.get("resultVariable", "ocr_text"))
        try:
            if mode == "region":
                image, region = await asyncio.to_thread(
                    self._capture_region, config, context
                )
            else:
                image_path = self.get_text(config.get("imagePath", ""), context)
                if not image_path:
                    return ModuleResult(success=False, error="图片路径不能为空")
                try:
                    content = await _read_image(context, image_path)
                except FileNotFoundError:
                    return ModuleResult(
                        success=False, error=f"图片不存在: {image_path}"
                    )
                from PIL import Image

                image = Image.open(io.BytesIO(content))
                region = None
            _raise_if_cancelled(context)
            text = await asyncio.to_thread(_recognize_image, image, ocr_type)
            _raise_if_cancelled(context)
            if variable_name:
                context.set_variable(variable_name, text)
            data: dict[str, Any] = {"text": text, "length": len(text)}
            if region is not None:
                data["region"] = region
            prefix = "区域OCR识别完成" if region is not None else "OCR识别完成"
            return ModuleResult(
                success=True,
                message=f"{prefix}: {text[:50]}{'...' if len(text) > 50 else ''}",
                data=data,
            )
        except ImportError:
            return ModuleResult(success=False, error="OCR识别功能初始化失败")
        except ValueError as error:
            if str(error) in {
                "区域坐标不能为空",
                "坐标必须是数字",
                "区域尺寸必须大于0",
            }:
                return ModuleResult(success=False, error=str(error))
            return ModuleResult(success=False, error=f"OCR识别失败: {error}")
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"OCR识别失败: {error}")

    @staticmethod
    def _capture_region(
        config: dict[str, Any], context: ExecutionContext
    ) -> tuple[Any, dict[str, int]]:
        values = [
            context.resolve_value(config.get(key, ""))
            for key in ("startX", "startY", "endX", "endY")
        ]
        if any(value in (None, "") for value in values):
            raise ValueError("区域坐标不能为空")
        try:
            x1, y1, x2, y2 = (int(value) for value in values)
        except (TypeError, ValueError):
            raise ValueError("坐标必须是数字") from None
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        if x1 == x2 or y1 == y2:
            raise ValueError("区域尺寸必须大于0")
        from PIL import ImageGrab

        return ImageGrab.grab(bbox=(x1, y1, x2, y2)), {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
        }


MEDIA_RECOGNITION_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    FaceRecognitionExecutor,
    ImageOCRExecutor,
)
