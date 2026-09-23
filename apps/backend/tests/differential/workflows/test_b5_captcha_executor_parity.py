from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw, ImageFont

from autoflow.application.workflows.executors import captcha
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_captcha_harness.py")


class Mouse:
    async def move(self, *_args: Any, **_options: Any) -> None:
        return None

    async def down(self) -> None:
        return None

    async def up(self) -> None:
        return None


class Locator:
    def __init__(self, image: bytes) -> None:
        self.image = image

    async def wait_for(self, **_options: Any) -> None:
        return None

    async def get_attribute(self, name: str) -> str | None:
        if name != "src":
            return None
        return f"data:image/png;base64,{base64.b64encode(self.image).decode()}"

    async def screenshot(self, *, path: str | None = None) -> bytes:
        assert path is None
        return self.image

    async def bounding_box(self) -> dict[str, float]:
        return {"x": 10, "y": 20, "width": 20, "height": 10}

    async def fill(self, _value: str) -> None:
        return None

    async def click(self, **_options: Any) -> None:
        return None


class Page:
    def __init__(self, image: bytes) -> None:
        self.image = image
        self.mouse = Mouse()

    def locator(self, _selector: str) -> Locator:
        return Locator(self.image)


class Browser:
    def __init__(self, image: bytes) -> None:
        self.page = Page(image)

    def current_page(self) -> Page:
        return self.page

    def active_page(self) -> Page:
        return self.page


def _captcha_png() -> bytes:
    small = Image.new("RGB", (40, 15), "white")
    ImageDraw.Draw(small).text(
        (2, 1), "1234", font=ImageFont.load_default(), fill="black"
    )
    image = small.resize((160, 60), Image.Resampling.NEAREST)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _source(payload: dict[str, Any]) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        check=True,
        text=True,
        env=environment,
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize(
    ("module_type", "config"),
    [
        ("ocr_captcha", {"imageSelector": "img", "variableName": "code"}),
        ("ocr_captcha", {"imageSelector": ""}),
        ("slider_captcha", {"sliderSelector": "#slider", "targetDistance": 35}),
        ("slider_captcha", {"sliderSelector": ""}),
    ],
)
def test_captcha_output_and_variable_changes_match_frozen_source(
    monkeypatch: pytest.MonkeyPatch, module_type: str, config: dict[str, Any]
) -> None:
    image = _captcha_png()
    source = _source(
        {
            "type": module_type,
            "config": config,
            "image": base64.b64encode(image).decode(),
        }
    )

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(captcha.asyncio, "sleep", no_sleep)
    context = ExecutionContext(browser=Browser(image))
    result = asyncio.run(
        build_production_executor_registry().get(module_type).execute(config, context)
    )
    target = {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }
    assert target == source
