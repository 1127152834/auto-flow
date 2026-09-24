# mypy: ignore-errors
from __future__ import annotations

import asyncio
import base64
import json
import sys


class Mouse:
    async def move(self, *_args, **_options):
        return None

    async def down(self):
        return None

    async def up(self):
        return None


class Locator:
    def __init__(self, page):
        self.page = page

    async def get_attribute(self, name):
        return f"data:image/png;base64,{self.page.image}" if name == "src" else None

    async def screenshot(self):
        return base64.b64decode(self.page.image)

    async def bounding_box(self):
        return {"x": 10, "y": 20, "width": 20, "height": 10}


class Page:
    def __init__(self, image):
        self.image = image
        self.mouse = Mouse()

    def locator(self, _selector):
        return Locator(self)

    async def fill(self, *_args):
        return None

    async def click(self, *_args):
        return None


from app.executors import captcha
from app.executors.base import ExecutionContext


async def _no_sleep(_seconds):
    return None


captcha.asyncio.sleep = _no_sleep


async def run(payload):
    executor = {
        "ocr_captcha": captcha.OCRCaptchaExecutor,
        "slider_captcha": captcha.SliderCaptchaExecutor,
    }[payload["type"]]()
    context = ExecutionContext(
        page=Page(payload.get("image", "")), variables=payload.get("variables", {})
    )
    result = await executor.execute(payload["config"], context)
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(json.load(sys.stdin))), ensure_ascii=False))
