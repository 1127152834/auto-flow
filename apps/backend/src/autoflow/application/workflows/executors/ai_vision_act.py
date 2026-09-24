"""WebRPA visual-action executor adapted to the CloakBrowser page.

Source: reference/WebRPA/backend/app/executors/advanced_vision_act.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: managed model IDs replace embedded credentials; CloakBrowser page screenshots
and page-scoped mouse actions replace Windows desktop capture and SendInput.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .ai import invoke_managed_messages
from .base import ModuleExecutor, ModuleResult

_SYSTEM_PROMPT = (
    "你是一个屏幕视觉定位引擎。用户会给你一张页面截图和一个目标描述，"
    "请找到该目标在图中的位置，返回它的中心点坐标。"
    "坐标用 0~1000 的归一化网格表示：左上角 (0,0)，右下角 (1000,1000)。"
    '只输出 JSON：{"found": true/false, "x": 数字, "y": 数字, "reason": "简短说明"}，'
    "找不到目标时 found 为 false。不要输出任何多余文字、不要用代码块包裹。"
)


def _extract_point(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    value = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", value)
    if fenced:
        value = fenced.group(1).strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        try:
            parsed = json.loads(value[start : end + 1]) if 0 <= start < end else None
        except json.JSONDecodeError:
            parsed = None
    if isinstance(parsed, dict):
        return parsed
    numbers = re.findall(r"\d+(?:\.\d+)?", value)
    if len(numbers) >= 2:
        return {"found": True, "x": float(numbers[0]), "y": float(numbers[1])}
    return None


class AIVisionActExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "ai_vision_act"

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(config.get("modelId"), str) or not config["modelId"].strip():
            return False, "请选择主应用中的模型"
        if not isinstance(config.get("instruction"), str) or not config[
            "instruction"
        ].strip():
            return False, "请填写要操作的目标描述(instruction)"
        return True, ""

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        if context.browser is None:
            return ModuleResult(success=False, error="没有打开的页面")
        instruction = self.get_text(config.get("instruction", ""), context)
        if not instruction.strip():
            return ModuleResult(
                success=False, error="请填写要操作的目标描述(instruction)"
            )
        page = context.browser.current_page()
        viewport = page.viewport_size
        if not viewport:
            try:
                measured = await page.evaluate(
                    "() => ({ width: window.innerWidth, height: window.innerHeight })"
                )
                if isinstance(measured, dict):
                    width, height = measured.get("width"), measured.get("height")
                    if type(width) is int and type(height) is int and width > 0 and height > 0:
                        viewport = {"width": width, "height": height}
            except Exception:  # noqa: BLE001 - viewport fallback is best effort.
                viewport = None
        if not viewport or viewport.get("width", 0) <= 0 or viewport.get("height", 0) <= 0:
            return ModuleResult(success=False, error="无法获取当前页面视口尺寸")
        try:
            screenshot = await page.screenshot(full_page=False)
            content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(screenshot).decode("utf-8")
                    },
                },
                {
                    "type": "text",
                    "text": f"目标：{instruction}\n请返回该目标中心点的归一化坐标(0~1000)。",
                },
            ]
            result, _model_id = await invoke_managed_messages(
                config,
                context,
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                default_temperature=0.2,
            )
        except Exception as error:  # noqa: BLE001 - browser/provider errors become node errors.
            return ModuleResult(success=False, error=str(error) or "视觉模型调用失败")

        point = _extract_point(result.content)
        variable_name = config.get("variableName", "") or config.get(
            "resultVariable", ""
        )
        if not point or point.get("found") is False:
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(
                    variable_name, {"found": False, "x": None, "y": None}
                )
            reason = point.get("reason", "") if point else ""
            return ModuleResult(
                success=False,
                error=f"未在页面上定位到目标：{instruction}。{reason}",
            )
        try:
            raw_x, raw_y = point.get("x"), point.get("y")
            if raw_x is None or raw_y is None:
                raise ValueError
            normalized_x = float(raw_x)
            normalized_y = float(raw_y)
        except (TypeError, ValueError):
            return ModuleResult(
                success=False,
                error=f"视觉模型返回坐标无效：{result.content[:120]}",
            )

        width, height = viewport["width"], viewport["height"]
        if normalized_x <= 1.5 and normalized_y <= 1.5:
            x, y = int(normalized_x * width), int(normalized_y * height)
        elif normalized_x <= 1000 and normalized_y <= 1000:
            x = int(normalized_x / 1000 * width)
            y = int(normalized_y / 1000 * height)
        else:
            x, y = int(normalized_x), int(normalized_y)
        x, y = max(0, min(x, width - 1)), max(0, min(y, height - 1))
        stored = {"found": True, "x": x, "y": y}
        if isinstance(variable_name, str) and variable_name:
            context.set_variable(variable_name, stored)

        action = self.get_text(config.get("action", "click"), context).strip()
        if action == "locate":
            return ModuleResult(
                success=True,
                message=f"已定位「{instruction}」→ ({x}, {y})",
                data={"x": x, "y": y},
            )
        try:
            if action == "move":
                await page.mouse.move(x, y)
                message = f"已移动到「{instruction}」({x}, {y})"
            else:
                button = "right" if action == "right" else str(
                    config.get("button", "left") or "left"
                )
                clicks = 2 if action == "double" else 1
                await page.mouse.click(x, y, button=button, click_count=clicks)
                action_name = {"double": "双击", "right": "右键单击"}.get(
                    action, "单击"
                )
                message = f"已在「{instruction}」({x}, {y}) {action_name}"
        except Exception as error:  # noqa: BLE001 - browser errors become node errors.
            return ModuleResult(success=False, error=f"页面鼠标操作失败: {error}")
        return ModuleResult(success=True, message=message, data={"x": x, "y": y})
