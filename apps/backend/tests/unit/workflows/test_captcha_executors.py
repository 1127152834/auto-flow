from __future__ import annotations

import asyncio
import io
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.execution import ExecutionContext
from PIL import Image, ImageDraw


class Locator:
    def __init__(
        self,
        *,
        src: str | None = None,
        screenshot: bytes = b"PNG",
        box: dict[str, float] | None = None,
    ) -> None:
        self.src = src
        self.image = screenshot
        self.box = box
        self.waits: list[tuple[str, float | None]] = []
        self.fills: list[str] = []
        self.clicks = 0

    async def wait_for(
        self, *, state: str = "visible", timeout_ms: float | None = None
    ) -> None:
        self.waits.append((state, timeout_ms))

    async def get_attribute(self, name: str) -> str | None:
        assert name == "src"
        return self.src

    async def screenshot(self, *, path: str | None = None) -> bytes:
        assert path is None
        return self.image

    async def fill(self, value: str) -> None:
        self.fills.append(value)

    async def click(self, **_options: Any) -> None:
        self.clicks += 1

    async def bounding_box(self) -> dict[str, float] | None:
        return self.box


class Mouse:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    async def move(self, x: float, y: float, **options: Any) -> None:
        self.calls.append(("move", x, y, options))

    async def down(self) -> None:
        self.calls.append(("down",))

    async def up(self) -> None:
        self.calls.append(("up",))


class Page:
    def __init__(self, locators: dict[str, Locator]) -> None:
        self.locators = locators
        self.mouse = Mouse()

    def locator(self, selector: str) -> Locator:
        return self.locators[selector]


class Browser:
    def __init__(self, page: Page) -> None:
        self.page = page

    def current_page(self) -> Page:
        return self.page

    def active_page(self) -> Page:
        return self.page


@pytest.mark.asyncio
async def test_ocr_captcha_uses_page_image_and_preserves_fill_submit_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OCR:
        def classification(self, image: bytes) -> str:
            assert image == b"captcha-bytes"
            return "A7中9"

    monkeypatch.setitem(sys.modules, "ddddocr", SimpleNamespace(DdddOcr=OCR))
    image = Locator(src="data:image/png;base64,Y2FwdGNoYS1ieXRlcw==")
    input_box = Locator()
    submit = Locator()
    context = ExecutionContext(
        browser=Browser(Page({"#captcha": image, "#code": input_box, "#submit": submit}))
    )

    result = await build_production_executor_registry().get("ocr_captcha").execute(
        {
            "imageSelector": "#captcha",
            "inputSelector": "#code",
            "variableName": "captcha",
            "autoSubmit": True,
            "submitSelector": "#submit",
            "timeout": 12,
        },
        context,
    )

    assert result.success is True
    assert result.data == "A7中9"
    assert context.variables["captcha"] == "A7中9"
    assert input_box.fills == ["A7中9"]
    assert submit.clicks == 1
    assert image.waits == [("visible", 12_000)]


@pytest.mark.asyncio
async def test_ocr_captcha_reads_existing_frontend_result_variable_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OCR:
        def classification(self, image: bytes) -> str:
            assert image == b"PNG"
            return "1234"

    monkeypatch.setitem(sys.modules, "ddddocr", SimpleNamespace(DdddOcr=OCR))
    context = ExecutionContext(
        browser=Browser(Page({"img": Locator()})),
    )
    result = await build_production_executor_registry().get("ocr_captcha").execute(
        {"imageSelector": "img", "resultVariable": "captcha_text"}, context
    )

    assert result.success is True
    assert context.variables == {"captcha_text": "1234"}


@pytest.mark.asyncio
async def test_slider_captcha_uses_manual_distance_on_cloakbrowser_mouse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autoflow.application.workflows.executors import captcha

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(captcha.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(captcha.random, "randint", lambda start, end: end)
    monkeypatch.setattr(captcha.random, "uniform", lambda start, end: start)
    page = Page(
        {"#slider": Locator(box={"x": 10, "y": 20, "width": 20, "height": 10})}
    )
    result = await build_production_executor_registry().get("slider_captcha").execute(
        {"sliderSelector": "#slider", "targetDistance": "{distance}"},
        ExecutionContext(variables={"distance": 35}, browser=Browser(page)),
    )

    assert result.success is True
    assert result.message == "滑块验证完成，滑动距离: 35px"
    assert page.mouse.calls[0] == ("move", 20, 25, {})
    assert page.mouse.calls[1] == ("down",)
    assert page.mouse.calls[-1] == ("up",)
    assert page.mouse.calls[-2][1] == 55


@pytest.mark.asyncio
async def test_slider_captcha_releases_mouse_when_run_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autoflow.application.workflows.executors import captcha

    class Cancelled:
        cancelled = True

        def raise_if_cancelled(self) -> None:
            raise asyncio.CancelledError

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(captcha.asyncio, "sleep", no_sleep)
    page = Page(
        {"#slider": Locator(box={"x": 10, "y": 20, "width": 20, "height": 10})}
    )
    with pytest.raises(asyncio.CancelledError):
        await build_production_executor_registry().get("slider_captcha").execute(
            {"sliderSelector": "#slider", "targetDistance": 35},
            ExecutionContext(browser=Browser(page), cancellation=Cancelled()),
        )

    assert page.mouse.calls[-1] == ("up",)


@pytest.mark.parametrize("module_type", ["ocr_captcha", "slider_captcha"])
def test_captcha_family_is_registered_and_requires_cloakbrowser(module_type: str) -> None:
    executor = build_production_executor_registry().get(module_type)
    assert executor.requires_browser_for({}) is True


def test_slider_gap_detection_uses_frozen_opencv_template_match() -> None:
    from autoflow.application.workflows.executors.captcha import _find_gap_position

    background = Image.new("RGB", (120, 40), "white")
    ImageDraw.Draw(background).rectangle((63, 8, 79, 24), fill="black")
    gap = background.crop((55, 0, 88, 33))
    background_bytes = io.BytesIO()
    gap_bytes = io.BytesIO()
    background.save(background_bytes, format="PNG")
    gap.save(gap_bytes, format="PNG")

    assert _find_gap_position(background_bytes.getvalue(), gap_bytes.getvalue()) == 55
