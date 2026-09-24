"""WebRPA captcha executors adapted to the active CloakBrowser page.

Source: reference/WebRPA/backend/app/executors/captcha.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: page access uses AutoFlow's CloakBrowser session and shared locator path;
``resultVariable`` remains an alias for documents created by the frozen frontend.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import random
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_actions import wait_for_locator

from .base import ModuleExecutor, ModuleResult
from .basic import _active_page, _timeout_ms, _truthy


class OCRCaptchaExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "ocr_captcha"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        image_selector = self.get_text(config.get("imageSelector", ""), context)
        input_selector = self.get_text(config.get("inputSelector", ""), context)
        submit_selector = self.get_text(config.get("submitSelector", ""), context)
        variable_name = str(
            config.get("variableName") or config.get("resultVariable") or ""
        ).strip()
        if not image_selector:
            return ModuleResult(success=False, error="验证码图片选择器不能为空")
        page = _active_page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")

        try:
            import ddddocr  # type: ignore[import-untyped]

            image, _ = await wait_for_locator(
                page,
                image_selector,
                state="visible",
                timeout_ms=_timeout_ms(config, context),
                hints=config.get("selectorHints"),
            )
            src = await image.get_attribute("src")
            image_bytes = (
                base64.b64decode(src.split(",", 1)[1])
                if src and src.startswith("data:") and "," in src
                else await image.screenshot()
            )
            # ddddocr writes an advertisement to stdout during construction;
            # worker stdout is the structured parent-process protocol.
            with contextlib.redirect_stdout(io.StringIO()):
                ocr = ddddocr.DdddOcr()
            result = await asyncio.to_thread(ocr.classification, image_bytes)

            if variable_name:
                context.set_variable(variable_name, result)
            if input_selector:
                input_box, _ = await wait_for_locator(
                    page,
                    input_selector,
                    state="visible",
                    timeout_ms=_timeout_ms(config, context),
                )
                await input_box.fill(result)
            if _truthy(config.get("autoSubmit", False), context) and submit_selector:
                submit, _ = await wait_for_locator(
                    page,
                    submit_selector,
                    state="visible",
                    timeout_ms=_timeout_ms(config, context),
                )
                await submit.click()
            return ModuleResult(
                success=True, message=f"验证码识别结果: {result}", data=result
            )
        except ImportError:
            return ModuleResult(success=False, error="验证码识别功能初始化失败")
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"验证码识别失败: {error}")


def _find_gap_position(background: bytes, gap: bytes) -> int | None:
    import cv2  # type: ignore[import-untyped]
    import numpy as np  # type: ignore[import-untyped]

    background_image = cv2.imdecode(
        np.frombuffer(background, np.uint8), cv2.IMREAD_COLOR
    )
    gap_image = cv2.imdecode(np.frombuffer(gap, np.uint8), cv2.IMREAD_COLOR)
    if background_image is None or gap_image is None:
        return None
    background_edge = cv2.Canny(
        cv2.cvtColor(background_image, cv2.COLOR_BGR2GRAY), 100, 200
    )
    gap_edge = cv2.Canny(cv2.cvtColor(gap_image, cv2.COLOR_BGR2GRAY), 100, 200)
    matched = cv2.matchTemplate(background_edge, gap_edge, cv2.TM_CCOEFF_NORMED)
    return int(cv2.minMaxLoc(matched)[3][0])


class SliderCaptchaExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "slider_captcha"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        slider_selector = self.get_text(config.get("sliderSelector", ""), context)
        background_selector = self.get_text(
            config.get("backgroundSelector") or config.get("trackSelector") or "",
            context,
        )
        gap_selector = self.get_text(config.get("gapSelector", ""), context)
        target_distance = context.resolve_value(config.get("targetDistance", ""))
        if not slider_selector:
            return ModuleResult(success=False, error="滑块选择器不能为空")
        page = _active_page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")

        try:
            slider, _ = await wait_for_locator(
                page,
                slider_selector,
                state="visible",
                timeout_ms=_timeout_ms(config, context),
                hints=config.get("selectorHints"),
            )
            slider_box = await slider.bounding_box()
            if not slider_box:
                return ModuleResult(success=False, error="无法获取滑块位置")

            slide_distance: int | None = None
            if target_distance not in (None, ""):
                try:
                    slide_distance = int(float(str(target_distance).strip()))
                except (TypeError, ValueError):
                    pass
            if slide_distance is None and background_selector and gap_selector:
                try:
                    background, _ = await wait_for_locator(
                        page,
                        background_selector,
                        state="visible",
                        timeout_ms=_timeout_ms(config, context),
                    )
                    gap, _ = await wait_for_locator(
                        page,
                        gap_selector,
                        state="visible",
                        timeout_ms=_timeout_ms(config, context),
                    )
                    slide_distance = await asyncio.to_thread(
                        _find_gap_position,
                        await background.screenshot(),
                        await gap.screenshot(),
                    )
                except Exception:  # noqa: BLE001,S110 -- frozen fallback is 200px.
                    pass
            if slide_distance is None:
                slide_distance = 200

            start_x = slider_box["x"] + slider_box["width"] / 2
            start_y = slider_box["y"] + slider_box["height"] / 2
            await page.mouse.move(start_x, start_y)
            await page.mouse.down()
            try:
                current_x = start_x
                target_x = start_x + slide_distance
                while current_x < target_x:
                    if context.cancellation is not None:
                        context.cancellation.raise_if_cancelled()
                    current_x = min(current_x + random.randint(5, 20), target_x)
                    await page.mouse.move(current_x, start_y + random.randint(-2, 2))
                    await asyncio.sleep(random.uniform(0.01, 0.03))
            finally:
                await asyncio.shield(page.mouse.up())
            await asyncio.sleep(1)
            return ModuleResult(
                success=True,
                message=f"滑块验证完成，滑动距离: {slide_distance}px",
            )
        except Exception as error:  # noqa: BLE001 -- preserve frozen node errors.
            return ModuleResult(success=False, error=f"滑块验证失败: {error}")


CAPTCHA_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    OCRCaptchaExecutor,
    SliderCaptchaExecutor,
)
