"""One page/frame resolution path for execution and inspection."""
from collections.abc import Callable
from typing import Any


class NodeFailure(Exception):
    def __init__(self, code: str, message: str, path: list[str] | None = None):
        self.code, self.message, self.path = code, message, path or []


async def locate_scope(page: Any, frame_path: list[str], remaining: Callable[[], float]) -> Any:
    if page.is_closed():
        raise NodeFailure("workflow_page_closed", "当前网页已关闭")
    scope = page
    for index, selector in enumerate(frame_path):
        path = ["config", "framePath", str(index)]
        remaining()
        try:
            frames = scope.locator(selector)
            count = await frames.count()
            if count != 1:
                raise NodeFailure("workflow_frame_ambiguous" if count else "workflow_frame_missing",
                                  "框架路径必须唯一匹配一个 iframe" if count else "框架不存在", path)
            element = await frames.element_handle(timeout=remaining())
            try:
                if element is None or await element.evaluate("el => el.tagName.toLowerCase()") != "iframe":
                    raise NodeFailure("workflow_frame_invalid", "路径目标不是 iframe", path)
                scope = await element.content_frame()
                if scope is None or scope.is_detached():
                    raise NodeFailure("workflow_frame_detached", "目标框架已失效", path)
            finally:
                if element is not None:
                    await element.dispose()
        except NodeFailure:
            raise
        except Exception as error:
            raise NodeFailure("workflow_frame_invalid", "框架选择器无效或框架已变化", path) from error
    remaining()
    return scope


async def locate_element(page: Any, config: dict[str, Any], remaining: Callable[[], float]) -> Any:
    scope = await locate_scope(page, config.get("framePath", []), remaining)
    try:
        locator = scope.locator(config["selector"])
        await locator.count()  # Validate syntax even for hidden/detached waits.
        return locator.first
    except Exception as error:
        raise NodeFailure("workflow_selector_invalid", "元素选择器无效", ["config", "selector"]) from error
