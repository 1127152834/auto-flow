"""Element change trigger migrated from WebRPA@5ccb900e.

Source: backend/app/executors/trigger.py#ElementChangeTriggerExecutor.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import format_selector

from .base import ModuleExecutor, ModuleResult
from .basic import _active_page
from .type_utils import to_int

_OBSERVER = """
() => {
  const params = __PARAMS__;
  return new Promise((resolve, reject) => {
    const target = document.querySelector(params.selector);
    if (!target) { reject(new Error('未找到目标元素')); return; }
    const initialChildCount = target.children.length;
    let timeoutId = null;
    const observer = new MutationObserver((mutations) => {
      if (timeoutId) clearTimeout(timeoutId);
      observer.disconnect();
      const changes = [], addedNodes = [], removedNodes = [];
      for (const mutation of mutations) {
        if (mutation.type === 'childList') {
          for (const node of mutation.addedNodes) if (node.nodeType === 1) {
            addedNodes.push({tagName: node.tagName?.toLowerCase(), className: node.className,
              id: node.id, textContent: node.textContent?.substring(0, 100) || ''});
          }
          for (const node of mutation.removedNodes) if (node.nodeType === 1) {
            removedNodes.push({tagName: node.tagName?.toLowerCase(), className: node.className,
              id: node.id});
          }
          changes.push({type: 'childList', addedCount: mutation.addedNodes.length,
            removedCount: mutation.removedNodes.length});
        } else if (mutation.type === 'attributes') {
          changes.push({type: 'attributes', attributeName: mutation.attributeName,
            oldValue: mutation.oldValue,
            newValue: mutation.target.getAttribute(mutation.attributeName)});
        } else if (mutation.type === 'characterData') {
          changes.push({type: 'characterData', oldValue: mutation.oldValue,
            newValue: mutation.target.textContent});
        }
      }
      let lastAdded = null;
      for (let i = mutations.length - 1; i >= 0 && !lastAdded; i--)
        for (let j = mutations[i].addedNodes.length - 1; j >= 0; j--)
          if (mutations[i].addedNodes[j].nodeType === 1) {
            lastAdded = mutations[i].addedNodes[j]; break;
          }
      let newElementSelector = null, newElementText = '';
      if (lastAdded) {
        newElementText = lastAdded.textContent?.trim() || '';
        if (lastAdded.id) newElementSelector = '#' + lastAdded.id;
        else if (lastAdded.parentElement) {
          const index = Array.from(lastAdded.parentElement.children).indexOf(lastAdded);
          newElementSelector = params.selector + ' > ' + lastAdded.tagName.toLowerCase()
            + ':nth-child(' + (index + 1) + ')';
        }
      }
      resolve({success: true, changes, addedNodes, removedNodes, newElementSelector,
        newElementText, currentChildCount: target.children.length, initialChildCount,
        mutationCount: mutations.length});
    });
    observer.observe(target, {childList: params.observeType === 'childList',
      attributes: params.observeType === 'attributes',
      characterData: params.observeType === 'characterData', subtree: true,
      attributeOldValue: params.observeType === 'attributes',
      characterDataOldValue: params.observeType === 'characterData'});
    if (params.timeout > 0) timeoutId = setTimeout(() => {
      observer.disconnect(); reject(new Error(`监控超时（${params.timeout}秒）`));
    }, params.timeout * 1000);
  });
}
"""


class ElementChangeTriggerExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "element_change_trigger"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        selector = context.resolve_value(config.get("selector", ""))
        observe_type = str(config.get("observeType", "childList"))
        timeout = to_int(config.get("timeout", 0), 0, context)
        selector_variable = str(
            config.get("saveNewElementSelector", "new_element_selector")
        )
        change_variable = str(config.get("saveChangeInfo", "element_change_info"))
        if not selector:
            return ModuleResult(success=False, error="元素选择器不能为空")
        if context.browser is None:
            return ModuleResult(success=False, error="浏览器未初始化，请先打开网页")
        page = _active_page(context)
        if page is None:
            return ModuleResult(success=False, error="页面未初始化，请先打开网页")

        _log(context, "👁️ 子元素变化触发器已启动")
        if not context.node_uses_sensitive_values:
            _log(context, f"🎯 监控元素: {selector}")
            _log(context, f"📋 监控类型: {observe_type}")
        await context.send_progress("👁️ 开始监控元素变化...")
        try:
            try:
                await page.locator(format_selector(str(selector))).first.wait_for(
                    state="visible", timeout_ms=10000
                )
            except Exception:  # noqa: BLE001 - frozen node has a dedicated missing error.
                return ModuleResult(success=False, error=f"未找到元素: {selector}")
            params = json.dumps(
                {
                    "selector": str(selector),
                    "observeType": observe_type,
                    "timeout": timeout,
                },
                ensure_ascii=False,
            )
            observer_result = await page.evaluate(
                _OBSERVER.replace("__PARAMS__", params)
            )
            if not isinstance(observer_result, dict) or not observer_result.get(
                "success"
            ):
                return ModuleResult(success=False, error="MutationObserver监控失败")
            return _result(
                observer_result,
                observe_type=observe_type,
                selector_variable=selector_variable,
                change_variable=change_variable,
                context=context,
            )
        except Exception as error:  # noqa: BLE001 - browser errors become node results.
            message = str(error)
            if "监控超时" in message:
                return ModuleResult(
                    success=False, error=f"子元素变化触发器超时（{timeout}秒）"
                )
            return ModuleResult(success=False, error=f"子元素变化触发器失败: {message}")


def _result(
    result: dict[str, Any],
    *,
    observe_type: str,
    selector_variable: str,
    change_variable: str,
    context: ExecutionContext,
) -> ModuleResult:
    changes = result.get("changes", [])
    added = result.get("addedNodes", [])
    removed = result.get("removedNodes", [])
    new_selector = result.get("newElementSelector")
    new_text = result.get("newElementText", "")
    current_count = result.get("currentChildCount", 0)
    initial_count = result.get("initialChildCount", 0)
    mutation_count = result.get("mutationCount", 0)
    descriptions = []
    if added:
        descriptions.append(f"新增{len(added)}个元素")
    if removed:
        descriptions.append(f"删除{len(removed)}个元素")
    if not descriptions:
        descriptions.append("元素发生变化")
    _log(context, f"✅ 检测到变化: {', '.join(descriptions)}")
    _log(context, f"📊 子元素数量: {initial_count} → {current_count}")
    _log(context, f"🔄 变化次数: {mutation_count}")
    if new_selector and not context.node_uses_sensitive_values:
        _log(context, f"🎯 新增元素选择器: {new_selector}")
    if new_text and not context.node_uses_sensitive_values:
        _log(context, f"📝 新增元素内容: {str(new_text)[:100]}")
    change_info = {
        "changeType": "childList" if added or removed else observe_type,
        "previousCount": initial_count,
        "currentCount": current_count,
        "addedCount": len(added),
        "removedCount": len(removed),
        "mutationCount": mutation_count,
        "changes": changes,
        "addedNodes": added,
        "removedNodes": removed,
        "newElementText": new_text,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if change_variable:
        context.set_variable(change_variable, change_info)
    if new_selector and selector_variable:
        context.set_variable(selector_variable, new_selector)
        if not context.node_uses_sensitive_values:
            _log(context, f"🔍 生成的选择器: {new_selector}", level="debug")
            if new_text:
                _log(context, f"📄 元素文本内容: {str(new_text)[:100]}", level="debug")
    return ModuleResult(
        success=True,
        message=f"子元素变化触发器已触发: {', '.join(descriptions)}",
        data={
            **change_info,
            "newElementSelector": new_selector,
            "newElementText": new_text,
        },
    )


def _log(context: ExecutionContext, message: str, *, level: str = "info") -> None:
    context.log_records.append(
        {
            "timestamp": context.clock.now().isoformat(),
            "level": level,
            "message": message,
            "duration": 0,
            "nodeId": context.current_node_id or "",
        }
    )


ELEMENT_CHANGE_TRIGGER_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    ElementChangeTriggerExecutor,
)
