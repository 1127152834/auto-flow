"""Approved WebRPA advanced browser executors with AutoFlow adaptations.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/advanced_browser.py. Licensed under LICENSE.WebRPA.
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from autoflow.domain.workflows.browser import BrowserLocatorPort, BrowserPagePort
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_actions import wait_for_locator

from .base import ModuleExecutor, ModuleResult
from .registry import register_executor
from .type_utils import to_int

_MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
_MAX_IMAGE_BYTES = 64 * 1024 * 1024


def _raise_if_cancelled(context: ExecutionContext) -> None:
    if context.cancellation is not None:
        context.cancellation.raise_if_cancelled()


def _page(context: ExecutionContext) -> BrowserPagePort | None:
    if context.browser is None:
        return None
    try:
        active_page = getattr(context.browser, "active_page", None)
        return (
            active_page() if active_page is not None else context.browser.current_page()
        )
    except Exception:  # noqa: BLE001 -- browser state is serialized as a node result.
        return None


def _dynamic(value: object, name: str, owner: str) -> Any:
    method = getattr(value, name, None)
    if method is None:
        raise RuntimeError(f"{owner}不支持 {name}")
    return method


def _first(locator: BrowserLocatorPort) -> Any:
    return getattr(locator, "first", locator)


def _timeout_ms(config: Mapping[str, Any], context: ExecutionContext) -> int | None:
    value = to_int(config.get("timeout", 30), 30, context) * 1000
    return None if value == 0 else value


async def _locator(
    page: BrowserPagePort,
    selector: str,
    config: dict[str, Any],
    context: ExecutionContext,
    *,
    hints_key: str = "selectorHints",
    config_key: str = "selector",
    timeout_ms: float | None = None,
) -> BrowserLocatorPort:
    hints = config.get(hints_key)
    locator, used_selector = await wait_for_locator(
        page,
        selector,
        state="visible",
        timeout_ms=timeout_ms,
        hints=hints if isinstance(hints, Mapping) else None,
    )
    if used_selector != selector:
        config[config_key] = used_selector
    return locator


@register_executor
class SelectDropdownExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "select_dropdown"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        select_by = context.resolve_value(config.get("selectBy", "value"))
        value = context.resolve_value(config.get("value", ""))
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        timeout_ms = _timeout_ms(config, context)
        try:
            try:
                await page.wait_for_load_state(
                    "domcontentloaded", timeout_ms=float(timeout_ms or 0)
                )
            except Exception:  # noqa: BLE001,S110 -- frozen source ignores load failure.
                pass
            element = await _locator(
                page, str(selector), config, context, timeout_ms=timeout_ms
            )
            select_option = _dynamic(element, "select_option", "浏览器定位器")
            values = config.get("values")
            if isinstance(values, list) and values:
                try:
                    await select_option(value=[str(item) for item in values])
                    return ModuleResult(success=True, message=f"已多选: {values}")
                except Exception:  # noqa: BLE001,S110 -- frozen fallback uses one value.
                    pass
            try:
                if select_by == "value":
                    await select_option(value=value)
                elif select_by == "label":
                    await select_option(label=value)
                elif select_by == "index":
                    await select_option(index=int(value))
                return ModuleResult(success=True, message=f"已选择: {value}")
            except Exception as native_error:  # noqa: BLE001 -- custom controls are fallback.
                clicked = await self._select_custom(
                    page, element, str(select_by), value, timeout_ms
                )
                if clicked:
                    return ModuleResult(
                        success=True, message=f"已选择(自定义下拉): {value}"
                    )
                return ModuleResult(
                    success=False,
                    error=(
                        f"选择下拉框失败：原生 select 不可用（{native_error}），"
                        f"且未在自定义下拉组件中找到选项「{value}」。"
                        "可尝试改用「点击元素」先展开下拉，再「点击元素」选中目标项。"
                    ),
                )
        except Exception as error:  # noqa: BLE001 -- provider errors are node results.
            return ModuleResult(success=False, error=f"选择下拉框失败: {error}")

    async def _select_custom(
        self,
        page: BrowserPagePort,
        element: BrowserLocatorPort,
        select_by: str,
        value: Any,
        timeout_ms: float | None,
    ) -> bool:
        try:
            await _first(element).click(timeout=timeout_ms)
        except Exception:  # noqa: BLE001 -- preserve the frozen inner-trigger fallback.
            try:
                inner = _first(
                    element.locator("input,.el-select__wrapper,.el-input__wrapper")
                )
                await inner.click(timeout=3000)
            except Exception:  # noqa: BLE001,S110 -- option lookup may still work.
                pass
        await asyncio.sleep(0.35)
        target_text = str(value).strip()
        selectors = (
            ".el-select-dropdown__item",
            ".el-cascader-node__label",
            ".ant-select-item-option-content",
            ".ant-select-item-option",
            'li[role="option"]',
            '[role="option"]',
            ".el-option",
            "li.option",
        )
        for selector in selectors:
            options = page.locator(selector)
            try:
                count = await options.count()
            except Exception:  # noqa: BLE001,S112 -- try the next selector.
                continue
            if not count:
                continue
            if select_by == "index":
                try:
                    await _dynamic(options, "nth", "浏览器定位器")(int(value)).click(
                        timeout=3000
                    )
                    return True
                except Exception:  # noqa: BLE001,S112 -- try the next selector.
                    continue
            for index in range(min(count, 200)):
                try:
                    option = _dynamic(options, "nth", "浏览器定位器")(index)
                    if not await option.is_visible():
                        continue
                    text = (
                        await _dynamic(option, "inner_text", "浏览器定位器")()
                    ).strip()
                    if text == target_text or (target_text and target_text in text):
                        await option.click(timeout=3000)
                        return True
                except Exception:  # noqa: BLE001,S112 -- try the next option.
                    continue
        return False


@register_executor
class SetCheckboxExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "set_checkbox"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        checked_raw = config.get("checked", True)
        if isinstance(checked_raw, str):
            checked_raw = context.resolve_value(checked_raw)
        checked = checked_raw in [True, "true", "True", "1", 1]
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            element = await _locator(page, str(selector), config, context)
            method = "check" if checked else "uncheck"
            await _dynamic(element, method, "浏览器定位器")()
            return ModuleResult(
                success=True, message=f"复选框已{'勾选' if checked else '取消勾选'}"
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"设置复选框失败: {error}")


@register_executor
class DragElementExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "drag_element"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        source_selector = context.resolve_value(config.get("sourceSelector", ""))
        target_selector = context.resolve_value(config.get("targetSelector", ""))
        target_position = config.get("targetPosition")
        if not source_selector:
            return ModuleResult(success=False, error="源元素选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            source = await _locator(
                page,
                str(source_selector),
                config,
                context,
                config_key="sourceSelector",
            )
            if target_selector:
                target = await _locator(
                    page,
                    str(target_selector),
                    config,
                    context,
                    hints_key="targetSelectorHints",
                    config_key="targetSelector",
                )
                await _dynamic(source, "drag_to", "浏览器定位器")(target)
            elif isinstance(target_position, Mapping):
                box = await _dynamic(source, "bounding_box", "浏览器定位器")()
                if box:
                    start_x = box["x"] + box["width"] / 2
                    start_y = box["y"] + box["height"] / 2
                    end_x = target_position.get("x", start_x)
                    end_y = target_position.get("y", start_y)
                    mouse = _dynamic(page, "mouse", "浏览器页面")
                    await mouse.move(start_x, start_y)
                    await mouse.down()
                    await mouse.move(end_x, end_y, steps=10)
                    await mouse.up()
            return ModuleResult(success=True, message="拖拽完成")
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"拖拽元素失败: {error}")


@register_executor
class ScrollPageExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "scroll_page"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        direction = context.resolve_value(config.get("direction", "down"))
        distance = to_int(config.get("distance", 500), 500, context)
        selector = context.resolve_value(config.get("selector", ""))
        scroll_mode = context.resolve_value(config.get("scrollMode", "auto"))
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        delta_x = (
            distance
            if direction == "right"
            else -distance
            if direction == "left"
            else 0
        )
        delta_y = (
            distance if direction == "down" else -distance if direction == "up" else 0
        )
        try:
            if scroll_mode in {"wheel", "auto"}:
                try:
                    mouse = _dynamic(page, "mouse", "浏览器页面")
                    if selector:
                        element = _first(page.locator(str(selector)))
                        box = await _dynamic(element, "bounding_box", "浏览器定位器")()
                        if not box:
                            raise RuntimeError("无法获取元素位置")
                        await mouse.move(
                            box["x"] + box["width"] / 2,
                            box["y"] + box["height"] / 2,
                        )
                    else:
                        viewport = getattr(page, "viewport_size", None)
                        if viewport:
                            await mouse.move(
                                viewport["width"] / 2, viewport["height"] / 2
                            )
                    await mouse.wheel(delta_x, delta_y)
                    return ModuleResult(
                        success=True,
                        message=f"已滚动 {direction} {distance}px (鼠标滚轮)",
                    )
                except Exception:
                    if scroll_mode == "wheel":
                        raise
            expression = f"el => el.scrollBy({delta_x}, {delta_y})"
            if selector:
                await page.locator(str(selector)).evaluate(expression)
            else:
                evaluate = getattr(page, "evaluate", None)
                if evaluate is not None:
                    await evaluate(f"window.scrollBy({delta_x}, {delta_y})")
                else:
                    await page.locator("html").evaluate(
                        f"el => el.ownerDocument.defaultView.scrollBy({delta_x}, {delta_y})"
                    )
            return ModuleResult(
                success=True, message=f"已滚动 {direction} {distance}px"
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"滚动页面失败: {error}")


@register_executor
class UploadFileExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "upload_file"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        file_path = context.resolve_value(config.get("filePath", ""))
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        if not file_path:
            return ModuleResult(success=False, error="文件路径不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        normalized = str(Path(str(file_path)).resolve())
        if not Path(normalized).is_file():
            return ModuleResult(success=False, error=f"文件不存在: {normalized}")
        try:
            element = page.locator(str(selector))
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            input_type = await element.evaluate("el => el.type || ''")
            if tag_name == "input" and input_type == "file":
                await _dynamic(element, "set_input_files", "浏览器定位器")(normalized)
                return ModuleResult(success=True, message=f"已上传文件: {normalized}")
            choose_file = getattr(page, "choose_file", None)
            if choose_file is not None:
                timeout_ms = _timeout_ms(config, context)
                await choose_file(
                    lambda: element.click(timeout=timeout_ms),
                    normalized,
                    timeout_ms=float(min(timeout_ms or 5000, 5000)),
                )
                return ModuleResult(success=True, message=f"已上传文件: {normalized}")
            return ModuleResult(
                success=False,
                error="上传文件失败（所有策略均失败）: 浏览器运行时不支持文件选择器",
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"上传文件失败: {error}")


@register_executor
class DownloadFileExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "download_file"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        mode = context.resolve_value(config.get("downloadMode", "click"))
        trigger = context.resolve_value(config.get("triggerSelector", ""))
        url = context.resolve_value(config.get("downloadUrl", ""))
        save_path = context.resolve_value(config.get("savePath", ""))
        file_name = context.resolve_value(config.get("fileName", ""))
        variable_name = config.get("variableName", "")
        if mode != "url" and not trigger:
            return ModuleResult(success=False, error="触发元素选择器不能为空")
        if mode == "url" and not url:
            return ModuleResult(success=False, error="下载URL不能为空")
        if context.node_artifacts is None:
            return ModuleResult(success=False, error="下载产物存储未配置")
        try:
            if mode == "url":
                _raise_if_cancelled(context)
                if not file_name:
                    file_name = (
                        unquote(os.path.basename(urlparse(str(url)).path))
                        or "downloaded_file"
                    )
                async with httpx.AsyncClient(
                    timeout=60, follow_redirects=True
                ) as client:
                    content_buffer = bytearray()
                    async with client.stream("GET", str(url)) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            _raise_if_cancelled(context)
                            content_buffer.extend(chunk)
                            if len(content_buffer) > _MAX_DOWNLOAD_BYTES:
                                raise ValueError("下载文件超过 64 MiB 限制")
                    content = bytes(content_buffer)
            else:
                page = _page(context)
                if page is None:
                    return ModuleResult(success=False, error="没有打开的页面")
                locator = page.locator(str(trigger))
                download = await page.capture_download(lambda: locator.click())
                file_name = file_name or download.suggested_filename
                temporary_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False) as temporary:
                        temporary_path = Path(temporary.name)
                    await download.save_as(temporary_path)
                    if temporary_path.stat().st_size > _MAX_DOWNLOAD_BYTES:
                        raise ValueError("下载文件超过 64 MiB 限制")
                    content = temporary_path.read_bytes()
                finally:
                    if temporary_path is not None:
                        temporary_path.unlink(missing_ok=True)
            artifact_name = (
                os.path.join(str(save_path), str(file_name))
                if save_path
                else str(file_name)
            )
            _raise_if_cancelled(context)
            final_path = await context.node_artifacts.write_bytes(
                name=artifact_name,
                content=content,
                mime_type="application/octet-stream",
            )
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, final_path)
            return ModuleResult(
                success=True, message=f"已下载文件: {final_path}", data=final_path
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"下载文件失败: {error}")


@register_executor
class SaveImageExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "save_image"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        save_path = context.resolve_value(config.get("savePath", ""))
        variable_name = config.get("variableName", "")
        if not selector:
            return ModuleResult(success=False, error="选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        if context.node_artifacts is None:
            return ModuleResult(success=False, error="图片产物存储未配置")
        try:
            element = page.locator(str(selector))
            source = await element.get_attribute("src")
            if source and source.startswith("data:"):
                header, encoded = source.split(",", 1)
                if len(encoded) > ((_MAX_IMAGE_BYTES + 2) // 3) * 4:
                    raise ValueError("图片超过 64 MiB 限制")
                image_data = base64.b64decode(encoded, validate=True)
                mime_type = header[5:].split(";", 1)[0] or "image/png"
            else:
                image_data = await element.screenshot()
                mime_type = "image/png"
            if len(image_data) > _MAX_IMAGE_BYTES:
                raise ValueError("图片超过 64 MiB 限制")
            _raise_if_cancelled(context)
            final_path = await context.node_artifacts.write_bytes(
                name=str(save_path) or "saved_image.png",
                content=image_data,
                mime_type=mime_type,
            )
            if isinstance(variable_name, str) and variable_name:
                context.set_variable(variable_name, final_path)
            return ModuleResult(
                success=True, message=f"已保存图片: {final_path}", data=final_path
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"保存图片失败: {error}")


_CHILD_SELECTORS_JS = """
el => {
  const parentSelector = %s;
  const childSelector = %s;
  const children = childSelector === '*'
    ? Array.from(el.children)
    : Array.from(el.querySelectorAll(':scope > ' + childSelector));
  const allChildren = Array.from(el.children);
  return children.map(child => {
    if (child.id) return '#' + CSS.escape(child.id);
    if (child.className && typeof child.className === 'string') {
      const classes = child.className.trim().split(/\\s+/).filter(Boolean);
      if (classes.length) {
        const classSelector = '.' + classes.join('.');
        if (el.querySelectorAll(':scope > ' + classSelector).length === 1)
          return parentSelector + ' > ' + classSelector;
      }
    }
    return parentSelector + ' > ' + child.tagName.toLowerCase()
      + ':nth-child(' + (allChildren.indexOf(child) + 1) + ')';
  });
}
"""


@register_executor
class GetChildElementsExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "get_child_elements"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        parent_selector = context.resolve_value(config.get("parentSelector", ""))
        variable_name = config.get("variableName", "")
        child_selector = context.resolve_value(config.get("childSelector", "*")) or "*"
        if not parent_selector:
            return ModuleResult(success=False, error="父元素选择器不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            parent = page.locator(str(parent_selector))
            await parent.wait_for(state="attached", timeout_ms=None)
            script = _CHILD_SELECTORS_JS % (
                _json_string(parent_selector),
                _json_string(child_selector),
            )
            selectors = await parent.evaluate(script)
            context.set_variable(str(variable_name), selectors)
            return ModuleResult(
                success=True,
                message=f"已获取 {len(selectors)} 个子元素，保存到变量 {variable_name}",
                data=selectors,
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"获取子元素列表失败: {error}")


_SIBLING_SELECTORS_JS = """
el => {
  const includeSelf = %s;
  const siblingType = %s;
  if (!el.parentElement) return [];
  const parent = el.parentElement;
  const all = Array.from(parent.children);
  const index = all.indexOf(el);
  const siblings = siblingType === 'previous' ? all.slice(0, index)
    : siblingType === 'next' ? all.slice(index + 1)
    : all.filter((_, itemIndex) => includeSelf || itemIndex !== index);
  return siblings.map(sibling => {
    if (sibling.id) return '#' + CSS.escape(sibling.id);
    if (sibling.className && typeof sibling.className === 'string') {
      const classes = sibling.className.trim().split(/\\s+/).filter(Boolean);
      if (classes.length) {
        const classSelector = '.' + classes.join('.');
        if (document.querySelectorAll(classSelector).length === 1) return classSelector;
        if (parent.querySelectorAll(':scope > ' + classSelector).length === 1) {
          const parentSelector = parent.id ? '#' + CSS.escape(parent.id)
            : parent.className && typeof parent.className === 'string'
              ? '.' + parent.className.trim().split(/\\s+/).filter(Boolean).join('.') : '';
          if (parentSelector) return parentSelector + ' > ' + classSelector;
        }
      }
    }
    const parentSelector = parent.id ? '#' + CSS.escape(parent.id)
      : parent.className && typeof parent.className === 'string'
        ? '.' + parent.className.trim().split(/\\s+/).filter(Boolean).join('.')
        : parent.tagName.toLowerCase();
    return parentSelector + ' > ' + sibling.tagName.toLowerCase()
      + ':nth-child(' + (all.indexOf(sibling) + 1) + ')';
  });
}
"""


def _json_string(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


@register_executor
class GetSiblingElementsExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "get_sibling_elements"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        element_selector = context.resolve_value(config.get("elementSelector", ""))
        variable_name = config.get("variableName", "")
        include_self = config.get("includeSelf", False)
        sibling_type = context.resolve_value(config.get("siblingType", "all")) or "all"
        if not element_selector:
            return ModuleResult(success=False, error="元素选择器不能为空")
        if not variable_name:
            return ModuleResult(success=False, error="变量名不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(success=False, error="没有打开的页面")
        try:
            element = page.locator(str(element_selector))
            await element.wait_for(state="attached", timeout_ms=None)
            script = _SIBLING_SELECTORS_JS % (
                "true" if include_self else "false",
                _json_string(sibling_type),
            )
            selectors = await element.evaluate(script)
            context.set_variable(str(variable_name), selectors)
            description = {
                "all": "所有",
                "previous": "前面的",
                "next": "后面的",
            }.get(str(sibling_type), "所有")
            return ModuleResult(
                success=True,
                message=(
                    f"已获取 {len(selectors)} 个{description}兄弟元素，"
                    f"保存到变量 {variable_name}"
                ),
                data=selectors,
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"获取兄弟元素列表失败: {error}")


@register_executor
class ElementExistsExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "element_exists"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        if not selector:
            return ModuleResult(success=False, error="元素选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(
                success=False, error="没有打开的页面，请先使用'打开网页'模块"
            )
        try:
            count = await page.locator(str(selector)).count()
            exists = count > 0
            return ModuleResult(
                success=True,
                message=f"元素存在（共找到 {count} 个匹配元素）"
                if exists
                else "元素不存在",
                branch="true" if exists else "false",
                data={"exists": exists, "count": count},
            )
        except Exception as error:  # noqa: BLE001 -- frozen predicate takes false branch.
            return ModuleResult(
                success=True,
                message=f"元素不存在（检查时出错: {error}）",
                branch="false",
                data={"exists": False, "error": str(error)},
            )


@register_executor
class ElementVisibleExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "element_visible"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        if not selector:
            return ModuleResult(success=False, error="元素选择器不能为空")
        page = _page(context)
        if page is None:
            return ModuleResult(
                success=False, error="没有打开的页面，请先使用'打开网页'模块"
            )
        try:
            element = page.locator(str(selector))
            count = await element.count()
            visible = await _first(element).is_visible() if count > 0 else False
            if visible:
                message = f"元素可见（共找到 {count} 个匹配元素）"
            elif count > 0:
                message = f"元素存在但不可见（共找到 {count} 个匹配元素）"
            else:
                message = "元素不存在"
            return ModuleResult(
                success=True,
                message=message,
                branch="true" if visible else "false",
                data={"visible": visible, "exists": count > 0, "count": count},
            )
        except Exception as error:  # noqa: BLE001 -- frozen predicate takes false branch.
            return ModuleResult(
                success=True,
                message=f"元素不可见（检查时出错: {error}）",
                branch="false",
                data={"visible": False, "error": str(error)},
            )


ADVANCED_BROWSER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    SelectDropdownExecutor,
    SetCheckboxExecutor,
    DragElementExecutor,
    ScrollPageExecutor,
    UploadFileExecutor,
    DownloadFileExecutor,
    SaveImageExecutor,
    GetChildElementsExecutor,
    GetSiblingElementsExecutor,
    ElementExistsExecutor,
    ElementVisibleExecutor,
)
