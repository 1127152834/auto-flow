from __future__ import annotations

# Source: WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb
# backend/app/services/recorder.py. Adapted to the AutoFlow-owned browser worker.
import asyncio
import json
import re
from contextlib import suppress
from typing import Any

RECORDER_SCRIPT = '(function () {\n  var KEY = \'__webrpa_rec\';\n  function recording() { return !window.__webrpaRecorderDisabled; }\n\n  function pushEvent(ev) {\n    if (!recording()) return;\n    try {\n      var arr = JSON.parse(sessionStorage.getItem(KEY) || \'[]\');\n      var last = arr.length ? arr[arr.length - 1] : null;\n      if (ev.type === \'input\' && last && last.type === \'input\' && last.selector === ev.selector) {\n        arr[arr.length - 1] = ev;\n      } else if (ev.type === \'scroll\' && last && last.type === \'scroll\' && (last.dy > 0) === (ev.dy > 0)) {\n        last.dy = (last.dy || 0) + (ev.dy || 0); last.y = ev.y; last.ts = ev.ts;   // 合并连续同向滚动\n      } else if (ev.type === \'dblclick\') {\n        // 双击前浏览器会先派发两次单击，移除紧邻的同选择器单击，避免重复录入\n        var removed = 0;\n        while (arr.length && removed < 2) {\n          var l = arr[arr.length - 1];\n          if (l && l.type === \'click\' && l.selector === ev.selector) { arr.pop(); removed++; }\n          else break;\n        }\n        arr.push(ev);\n      } else if (ev.type === \'navigate\' && last && last.type === \'navigate\' && last.url === ev.url) {\n        // 跳过重复导航\n      } else {\n        arr.push(ev);\n      }\n      sessionStorage.setItem(KEY, JSON.stringify(arr));\n    } catch (e) {}\n  }\n\n  function cssEsc(s) {\n    if (window.CSS && CSS.escape) { try { return CSS.escape(s); } catch (e) {} }\n    return String(s).replace(/([^\\w-])/g, \'\\\\$1\');\n  }\n  function attrEsc(s) { return String(s).replace(/(["\\\\])/g, \'\\\\$1\'); }\n  // 唯一性校验：ctx 为查询根（普通元素=document；Shadow DOM 内元素=其 shadowRoot），\n  // 使选择器在正确的作用域内校验唯一。Playwright 的 CSS 定位默认穿透 open shadow，回放可命中。\n  function uniqueOK(sel, ctx) { try { return (ctx || document).querySelectorAll(sel).length === 1; } catch (e) { return false; } }\n  function rootOf(el) { try { var r = el.getRootNode && el.getRootNode(); return (r && r.querySelectorAll) ? r : document; } catch (e) { return document; } }\n\n  // id 是否为框架生成的不稳定值（React useId ":r1:"、hash、纯数字序号等）\n  function isBadId(id) {\n    if (!id) return true;\n    if (!/^[A-Za-z][\\w-]*$/.test(id)) return true;   // 含非法字符（如 :r1:、含空格）\n    if (id.length > 40) return true;\n    if (/[0-9a-f]{8,}/i.test(id)) return true;        // 长十六进制 / hash\n    if (/\\d{5,}/.test(id)) return true;               // 连续多位数字序号\n    if (/^(ember|ext-|mui-|radix-|headlessui-|react-aria-)/i.test(id)) return true;\n    return false;\n  }\n  // class 是否稳定（排除 CSS Module / CSS-in-JS / hash 生成的垃圾类名）\n  function isStableClass(c) {\n    if (!c || c.length > 30) return false;\n    if (/^[0-9]/.test(c)) return false;\n    if (/[0-9a-f]{6,}/i.test(c)) return false;        // 含 hash 片段\n    if (/\\d{3,}/.test(c)) return false;\n    if (/--|__[a-z0-9]{4,}/.test(c)) return false;    // CSS Module / BEM 生成后缀\n    if (/^(css|sc|jsx|jss|makeStyles|emotion)[-_]?/i.test(c)) return false; // CSS-in-JS 前缀\n    return true;\n  }\n  function stableClasses(el) {\n    if (!el.className || typeof el.className !== \'string\') return [];\n    return el.className.split(/\\s+/).filter(isStableClass);\n  }\n  function nthOfType(el) {\n    var p = el.parentElement; if (!p) return 0;\n    var same = Array.prototype.filter.call(p.children, function (c) { return c.tagName === el.tagName; });\n    if (same.length <= 1) return 0;\n    return same.indexOf(el) + 1;\n  }\n  // 元素自身的稳定唯一属性选择器；按稳定性从高到低尝试，找不到返回 \'\'\n  function attrSelector(el) {\n    if (!el || el.nodeType !== 1) return \'\';\n    var tag = el.tagName.toLowerCase();\n    var root = rootOf(el);\n    if (el.id && !isBadId(el.id)) {\n      var sid = \'#\' + cssEsc(el.id);\n      if (uniqueOK(sid, root)) return sid;\n    }\n    var testAttrs = [\'data-testid\', \'data-test\', \'data-cy\', \'data-qa\', \'data-test-id\', \'data-id\'];\n    for (var i = 0; i < testAttrs.length; i++) {\n      var tv = el.getAttribute && el.getAttribute(testAttrs[i]);\n      if (tv) { var st = \'[\' + testAttrs[i] + \'="\' + attrEsc(tv) + \'"]\'; if (uniqueOK(st, root)) return st; }\n    }\n    var nm = el.getAttribute && el.getAttribute(\'name\');\n    if (nm) { var sn = tag + \'[name="\' + attrEsc(nm) + \'"]\'; if (uniqueOK(sn, root)) return sn; }\n    var al = el.getAttribute && el.getAttribute(\'aria-label\');\n    if (al && al.length <= 50) { var sa = tag + \'[aria-label="\' + attrEsc(al) + \'"]\'; if (uniqueOK(sa, root)) return sa; }\n    var ph = el.getAttribute && el.getAttribute(\'placeholder\');\n    if (ph && ph.length <= 50) { var sp = \'[placeholder="\' + attrEsc(ph) + \'"]\'; if (uniqueOK(sp, root)) return sp; }\n    if (tag === \'a\') {\n      var href = el.getAttribute(\'href\');\n      if (href && href !== \'#\' && href.length <= 80) { var sh = \'a[href="\' + attrEsc(href) + \'"]\'; if (uniqueOK(sh, root)) return sh; }\n    }\n    return \'\';\n  }\n  function segmentFor(el) {\n    var seg = el.tagName.toLowerCase();\n    var cls = stableClasses(el);\n    if (cls.length) { seg += \'.\' + cls.slice(0, 2).join(\'.\'); }\n    else { var n = nthOfType(el); if (n > 0) seg += \':nth-of-type(\' + n + \')\'; }\n    return seg;\n  }\n  function computeSelector(el) {\n    if (!el || el.nodeType !== 1) return \'\';\n    // 1) 元素自身的稳定唯一属性（#id / data-* / name / aria-label / placeholder / a[href]）\n    var direct = attrSelector(el);\n    if (direct) return direct;\n    // 2) 就近稳定祖先锚定 + 短相对路径（抗页面结构变化）\n    var anchorSel = \'\', anchor = null, p = el.parentElement, hops = 0;\n    while (p && p !== document.body && p !== document.documentElement && hops < 10) {\n      var as = attrSelector(p);\n      if (as) { anchorSel = as; anchor = p; break; }\n      p = p.parentElement; hops++;\n    }\n    var parts = [], cur = el, stop = anchor || document.body, depth = 0;\n    while (cur && cur.nodeType === 1 && cur !== stop && cur !== document.body && cur !== document.documentElement && depth < 6) {\n      parts.unshift(segmentFor(cur));\n      cur = cur.parentElement; depth++;\n    }\n    var rel = parts.join(\' > \');\n    var root = rootOf(el);\n    if (anchorSel) {\n      var full = rel ? anchorSel + \' > \' + rel : anchorSel;\n      if (uniqueOK(full, root)) return full;\n      var loose = rel ? anchorSel + \' \' + rel : anchorSel;  // 放宽为后代组合，抗中间层增删\n      if (uniqueOK(loose, root)) return loose;\n      return full;\n    }\n    return rel || el.tagName.toLowerCase();\n  }\n  // 采集元素提示（供执行器"选择器自愈"锚点重定位；结构对应 base.build_fallback_selectors）\n  function collectHints(el) {\n    if (!el || el.nodeType !== 1) return null;\n    var tag = el.tagName.toLowerCase();\n    var attrs = {};\n    var wanted = [\'data-testid\', \'data-test\', \'data-cy\', \'data-qa\', \'data-id\', \'name\', \'placeholder\', \'aria-label\', \'role\', \'type\', \'href\', \'title\', \'alt\'];\n    for (var i = 0; i < wanted.length; i++) {\n      var v = el.getAttribute && el.getAttribute(wanted[i]);\n      if (v != null && v !== \'\') attrs[wanted[i]] = String(v).slice(0, 120);\n    }\n    var isField = (tag === \'input\' || tag === \'textarea\' || tag === \'select\');\n    var text = isField ? \'\' : (el.innerText || el.textContent || \'\').replace(/\\s+/g, \' \').trim().slice(0, 60);\n    return {\n      tag: tag,\n      attributes: attrs,\n      id: (el.id && !isBadId(el.id)) ? el.id : \'\',\n      name: (el.getAttribute && el.getAttribute(\'name\')) || \'\',\n      className: stableClasses(el).slice(0, 3).join(\' \'),\n      placeholder: (el.getAttribute && el.getAttribute(\'placeholder\')) || \'\',\n      ariaLabel: (el.getAttribute && el.getAttribute(\'aria-label\')) || \'\',\n      testid: (el.getAttribute && (el.getAttribute(\'data-testid\') || el.getAttribute(\'data-test\') || el.getAttribute(\'data-cy\') || el.getAttribute(\'data-qa\') || el.getAttribute(\'data-id\'))) || \'\',\n      text: text\n    };\n  }\n\n  // 从点击目标向上查找最近的"语义可点击元素"（按钮/链接/角色控件），\n  // 避免录到按钮内部的 <span>/<svg> 图标 —— 这类内部元素往往无稳定选择器。\n  function clickableTarget(el) {\n    var CLICKABLE = { a: 1, button: 1, summary: 1, label: 1 };\n    var ROLES = { button: 1, link: 1, menuitem: 1, menuitemcheckbox: 1, menuitemradio: 1, tab: 1, option: 1, checkbox: 1, radio: 1, \'switch\': 1 };\n    var cur = el, hops = 0;\n    while (cur && cur.nodeType === 1 && cur !== document.body && hops < 5) {\n      var tag = cur.tagName.toLowerCase();\n      if (CLICKABLE[tag]) return cur;\n      if (tag === \'input\') {\n        var t = (cur.type || \'\').toLowerCase();\n        if (t === \'button\' || t === \'submit\' || t === \'reset\' || t === \'checkbox\' || t === \'radio\') return cur;\n      }\n      var role = cur.getAttribute && cur.getAttribute(\'role\');\n      if (role && ROLES[role.toLowerCase()]) return cur;\n      if (cur.hasAttribute && (cur.hasAttribute(\'onclick\') || cur.getAttribute(\'tabindex\') === \'0\')) return cur;\n      cur = cur.parentElement; hops++;\n    }\n    return el;  // 找不到语义祖先则回退原元素\n  }\n  // 优先取无障碍/标题文本作为节点名称，兜底 innerText/value\n  function bestText(el) {\n    var t = (el.getAttribute && (el.getAttribute(\'aria-label\') || el.getAttribute(\'title\'))) || el.innerText || el.value || \'\';\n    return String(t).replace(/\\s+/g, \' \').trim().slice(0, 60);\n  }\n  // 忠实优先：录用户实际点击的元素；仅当该元素无法生成"唯一稳定"选择器时，\n  // 才回退到最近的语义可点击祖先（点击效果等价——事件会向上冒泡，同时选择器更稳）。\n  function resolveClickable(raw) {\n    var sel = computeSelector(raw);\n    if (uniqueOK(sel)) return { el: raw, selector: sel };\n    var alt = clickableTarget(raw);\n    if (alt && alt !== raw) {\n      var altSel = computeSelector(alt);\n      if (uniqueOK(altSel)) return { el: alt, selector: altSel };\n    }\n    return { el: raw, selector: sel };\n  }\n  // 向上查找 draggable 祖先（HTML5 拖拽的拖动源常在祖先上）\n  function draggableTarget(el) {\n    var cur = el, hops = 0;\n    while (cur && cur.nodeType === 1 && cur !== document.body && hops < 4) {\n      if (cur.getAttribute && cur.getAttribute(\'draggable\') === \'true\') return cur;\n      cur = cur.parentElement; hops++;\n    }\n    return el;\n  }\n  function ensureBadge() {\n    try {\n      // 角标只在顶层窗口显示；iframe（含跨域）内不注入，避免污染子框架\n      try { if (window.top !== window.self) return; } catch (e) { return; }\n      if (recording()) {\n        if (!document.getElementById(\'__webrpa_rec_badge\')) {\n          var badge = document.createElement(\'div\');\n          badge.id = \'__webrpa_rec_badge\';\n          badge.style.cssText = \'position:fixed;top:10px;right:10px;z-index:2147483647;background:#dc2626;color:#fff;padding:6px 12px;border-radius:999px;font:600 12px sans-serif;box-shadow:0 4px 12px rgba(0,0,0,.3);pointer-events:none;display:flex;align-items:center;gap:6px;\';\n          badge.innerHTML = \'<span style="width:8px;height:8px;border-radius:50%;background:#fff;display:inline-block;animation:wrpaBlink 1s infinite;"></span>WebRPA 录制中\';\n          var st = document.createElement(\'style\'); st.textContent = \'@keyframes wrpaBlink{0%,100%{opacity:1}50%{opacity:.25}}\';\n          (document.head || document.documentElement).appendChild(st);\n          (document.body || document.documentElement).appendChild(badge);\n        }\n      } else {\n        var b = document.getElementById(\'__webrpa_rec_badge\'); if (b) b.remove();\n      }\n    } catch (e) {}\n  }\n\n  // 事件监听器只挂一次（永不重复）\n  if (!window.__webrpaRecorderListenersAttached) {\n    window.__webrpaRecorderListenersAttached = true;\n\n    // 拖拽状态（供 click 抑制、去重使用）\n    var __md = null;                 // mousedown 起点 {el,x,y,dragging}\n    var __suppressClickUntil = 0;    // 拖拽结束后短时间内抑制误触发的 click\n    var __htmlDragActive = false;    // HTML5 原生拖拽进行中（避免与 mouse 版重复）\n\n    document.addEventListener(\'click\', function (e) {\n      if (!e.isTrusted) return;   // 只录真实用户操作，忽略页面脚本派发的合成事件（避免一次点击录出多条）\n      if (e.button && e.button !== 0) return;   // 只录左键，忽略右键/中键（右键菜单等原生行为不录）\n      if (Date.now() < __suppressClickUntil) return;  // 拖拽刚结束，抑制误触 click\n      // composedPath()[0] 取 Shadow DOM 内真实元素（e.target 会被重定向到 shadow 宿主）\n      var raw = (e.composedPath && e.composedPath()[0]) || e.target;\n      if (!raw || raw.id === \'__webrpa_rec_badge\') return;\n      var r = resolveClickable(raw), el = r.el;\n      var tag = (el.tagName || \'\').toLowerCase();\n      if (tag === \'option\') return;\n      if (tag === \'select\') return;  // 原生下拉的选择由 change 事件（select）负责，点击不另录\n      // 原生勾选控件的点击由 change 事件（check）负责，避免重复录\n      var t0 = (el.type || \'\').toLowerCase();\n      if (tag === \'input\' && (t0 === \'checkbox\' || t0 === \'radio\')) return;\n      if (tag === \'label\') {\n        try {\n          var ctrl = el.control || (el.htmlFor ? document.getElementById(el.htmlFor) : null);\n          if (ctrl) { var ct = (ctrl.type || \'\').toLowerCase(); if (ct === \'checkbox\' || ct === \'radio\') return; }\n        } catch (_) {}\n      }\n      pushEvent({ type: \'click\', selector: r.selector, hints: collectHints(el), tag: tag,\n        text: bestText(el), url: location.href, ts: Date.now() });\n    }, true);\n\n    document.addEventListener(\'dblclick\', function (e) {\n      if (!e.isTrusted) return;\n      if (e.button && e.button !== 0) return;\n      var raw = (e.composedPath && e.composedPath()[0]) || e.target;\n      if (!raw || raw.id === \'__webrpa_rec_badge\') return;\n      var r = resolveClickable(raw), el = r.el;\n      var tag = (el.tagName || \'\').toLowerCase();\n      if (tag === \'option\') return;\n      pushEvent({ type: \'dblclick\', selector: r.selector, hints: collectHints(el), tag: tag,\n        text: bestText(el), url: location.href, ts: Date.now() });\n    }, true);\n\n    document.addEventListener(\'change\', function (e) {\n      if (!e.isTrusted) return;\n      var el = (e.composedPath && e.composedPath()[0]) || e.target; if (!el) return;\n      var tag = (el.tagName || \'\').toLowerCase(), t = (el.type || \'\').toLowerCase();\n      if (t === \'file\') {\n        // 浏览器安全禁止读取真实路径，无法回放原文件；仍生成"上传文件"占位节点（含选择器+文件名提示），用户只需补填路径\n        var fn = \'\';\n        try { if (el.files && el.files.length) fn = el.files[0].name; } catch (_) {}\n        pushEvent({ type: \'upload\', selector: computeSelector(el), hints: collectHints(el), fileName: fn, url: location.href, ts: Date.now() });\n        return;\n      }\n      if (tag === \'select\') {\n        if (el.multiple) {\n          // 多选下拉：忠实记录所有选中项，避免只录首个导致回放不等价\n          var vals = [], txts = [];\n          for (var oi = 0; oi < el.options.length; oi++) {\n            if (el.options[oi].selected) { vals.push(el.options[oi].value); txts.push(el.options[oi].text); }\n          }\n          pushEvent({ type: \'select\', selector: computeSelector(el), hints: collectHints(el), value: el.value, values: vals, text: txts.join(\', \'), url: location.href, ts: Date.now() });\n        } else {\n          var opt = el.options[el.selectedIndex];\n          pushEvent({ type: \'select\', selector: computeSelector(el), hints: collectHints(el), value: el.value, text: opt ? opt.text : \'\', url: location.href, ts: Date.now() });\n        }\n      } else if (tag === \'input\' || tag === \'textarea\') {\n        if (t === \'checkbox\' || t === \'radio\') pushEvent({ type: \'check\', selector: computeSelector(el), hints: collectHints(el), value: !!el.checked, url: location.href, ts: Date.now() });\n        else pushEvent({ type: \'input\', selector: computeSelector(el), hints: collectHints(el), value: el.value, sensitive: (t === \'password\'), url: location.href, ts: Date.now() });\n      } else if (el.isContentEditable) {\n        pushEvent({ type: \'input\', selector: computeSelector(el), hints: collectHints(el), value: el.innerText, url: location.href, ts: Date.now() });\n      }\n    }, true);\n\n    document.addEventListener(\'input\', function (e) {\n      if (!e.isTrusted) return;\n      var el = (e.composedPath && e.composedPath()[0]) || e.target; if (!el) return;\n      var tag = (el.tagName || \'\').toLowerCase(), t = (el.type || \'\').toLowerCase();\n      if (t === \'file\') return;\n      if ((tag === \'input\' && t !== \'checkbox\' && t !== \'radio\') || tag === \'textarea\')\n        pushEvent({ type: \'input\', selector: computeSelector(el), hints: collectHints(el), value: el.value, sensitive: (t === \'password\'), url: location.href, ts: Date.now() });\n      else if (el.isContentEditable)\n        pushEvent({ type: \'input\', selector: computeSelector(el), hints: collectHints(el), value: el.innerText, url: location.href, ts: Date.now() });\n    }, true);\n\n    document.addEventListener(\'keydown\', function (e) {\n      if (!e.isTrusted) return;\n      var k = e.key;\n      var special = [\'Enter\',\'Tab\',\'Escape\',\'ArrowUp\',\'ArrowDown\',\'ArrowLeft\',\'ArrowRight\',\'Backspace\',\'Delete\',\'Home\',\'End\',\'PageUp\',\'PageDown\'];\n      var combo = e.ctrlKey || e.altKey || e.metaKey;\n      if (special.indexOf(k) === -1 && !combo) return;\n      if (k === \'Control\' || k === \'Alt\' || k === \'Meta\' || k === \'Shift\') return;\n      // 编辑框内的方向/删除键属于打字过程本身，不单独录（Enter/Tab/Escape 与组合键仍录，含语义）\n      var a = (e.composedPath && e.composedPath()[0]) || e.target;\n      var ed = false;\n      try { var atag = (a && a.tagName || \'\').toLowerCase(); ed = (atag === \'input\' || atag === \'textarea\' || (a && a.isContentEditable)); } catch (_) {}\n      var editKeys = [\'ArrowUp\',\'ArrowDown\',\'ArrowLeft\',\'ArrowRight\',\'Backspace\',\'Delete\',\'Home\',\'End\',\'PageUp\',\'PageDown\'];\n      if (ed && !combo && editKeys.indexOf(k) !== -1) return;\n      var seq = (e.ctrlKey ? \'Control+\' : \'\') + (e.altKey ? \'Alt+\' : \'\') + (e.metaKey ? \'Meta+\' : \'\') + (e.shiftKey && combo ? \'Shift+\' : \'\') + k;\n      // 在输入类元素上按键时记录其选择器：回放定位到该元素再按键，忠实还原按键作用目标\n      var kt = null;\n      if (ed) { try { kt = computeSelector(a); } catch (_) {} }\n      pushEvent({ type: \'keypress\', key: seq, selector: kt, url: location.href, ts: Date.now() });\n    }, true);\n\n    // 拖拽录制（自定义拖拽/滑块/排序）：mousedown→move 超阈值→mouseup 生成 drag 事件\n    document.addEventListener(\'mousedown\', function (e) {\n      if (!e.isTrusted) return;\n      if (e.button && e.button !== 0) return;\n      var raw = e.target; if (!raw || raw.id === \'__webrpa_rec_badge\') { __md = null; return; }\n      __md = { el: raw, x: e.clientX, y: e.clientY, dragging: false };\n    }, true);\n    document.addEventListener(\'mousemove\', function (e) {\n      if (!__md || __md.dragging) return;\n      var dx = e.clientX - __md.x, dy = e.clientY - __md.y;\n      if (dx * dx + dy * dy > 64) __md.dragging = true;   // 位移 > 8px 判定为拖拽\n    }, true);\n    document.addEventListener(\'mouseup\', function (e) {\n      if (!e.isTrusted) { return; }\n      var md = __md; __md = null;\n      if (!md || !md.dragging) return;          // 普通点击交给 click 处理\n      if (__htmlDragActive) return;             // HTML5 拖拽已由 drop 记录，避免重复\n      var srcEl = draggableTarget(md.el), tgtEl = (e.composedPath && e.composedPath()[0]) || e.target;\n      if (!srcEl || !tgtEl) return;\n      __suppressClickUntil = Date.now() + 400;  // 抑制拖拽尾随的 click\n      pushEvent({ type: \'drag\', selector: computeSelector(srcEl), targetSelector: computeSelector(tgtEl),\n        endX: Math.round(e.clientX), endY: Math.round(e.clientY),\n        hints: collectHints(srcEl), targetHints: collectHints(tgtEl), text: bestText(srcEl), url: location.href, ts: Date.now() });\n    }, true);\n\n    // HTML5 原生拖拽（draggable=true + drop 目标）\n    document.addEventListener(\'dragstart\', function (e) {\n      if (!e.isTrusted) return;\n      __htmlDragActive = true;\n      __md = { el: draggableTarget(e.target), x: 0, y: 0, dragging: true };\n    }, true);\n    document.addEventListener(\'dragend\', function () {\n      setTimeout(function () { __htmlDragActive = false; }, 50);\n      __md = null;\n    }, true);\n    document.addEventListener(\'drop\', function (e) {\n      if (!e.isTrusted) return;\n      var md = __md;\n      if (!md || !md.el) { __htmlDragActive = false; return; }\n      var srcEl = md.el, tgtEl = (e.composedPath && e.composedPath()[0]) || e.target;\n      __suppressClickUntil = Date.now() + 400;\n      pushEvent({ type: \'drag\', selector: computeSelector(srcEl), targetSelector: computeSelector(tgtEl),\n        endX: Math.round(e.clientX), endY: Math.round(e.clientY),\n        hints: collectHints(srcEl), targetHints: collectHints(tgtEl), text: bestText(srcEl), url: location.href, ts: Date.now() });\n    }, true);\n\n    // 页面滚动：防抖 + 阈值过滤 + 合并连续同向，避免细碎噪音（记录净位移，回放按距离滚动）\n    var __scrollTimer = null, __lastScrollY = (window.scrollY || (document.documentElement ? document.documentElement.scrollTop : 0) || 0);\n    window.addEventListener(\'scroll\', function () {\n      if (!recording()) return;\n      if (__scrollTimer) clearTimeout(__scrollTimer);\n      __scrollTimer = setTimeout(function () {\n        var y = window.scrollY || (document.documentElement ? document.documentElement.scrollTop : 0) || 0;\n        var dy = y - __lastScrollY; __lastScrollY = y;\n        if (Math.abs(dy) < 80) return;   // 过滤细碎滚动\n        pushEvent({ type: \'scroll\', dy: dy, y: y, url: location.href, ts: Date.now() });\n      }, 400);\n    }, true);\n  }\n\n  // 每次脚本执行（页面加载/手动注入）：刷新角标 + 记录一次导航\n  ensureBadge();\n  pushEvent({ type: \'navigate\', url: location.href, ts: Date.now() });\n})();'

RECORDER_SCRIPT = RECORDER_SCRIPT.replace(
    "  function pushEvent(ev) {\n    if (!recording()) return;",
    "  function pushEvent(ev) {\n    if (!recording()) return;\n"
    "    if (!ev.__autoflowRecordId) ev.__autoflowRecordId = "
    "Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);",
).replace(
    "      sessionStorage.setItem(KEY, JSON.stringify(arr));",
    "      sessionStorage.setItem(KEY, JSON.stringify(arr));\n"
    "      try { if (typeof window.__autoflowRecordCdp === 'function') "
    "window.__autoflowRecordCdp(JSON.stringify(ev)); } catch (_) {}\n"
    "      try { if (typeof window.__autoflowRecordEvent === 'function') "
    "window.__autoflowRecordEvent(ev).catch(function(){}); } catch (_) {}",
)

_DRAIN_JS = "() => {\n  try {\n    var arr = JSON.parse(sessionStorage.getItem('__webrpa_rec') || '[]');\n    sessionStorage.setItem('__webrpa_rec', '[]');\n    return arr;\n  } catch (e) { return []; }\n}"

class RecorderController:
    def __init__(self, browser: Any) -> None:
        self.browser = browser
        self.active = False
        self._registered = False
        self._binding_registered = False
        self._cdp_registered = False
        self._cdp_sessions: dict[int, Any] = {}
        self._cdp_contexts: dict[tuple[int, int], dict[str, Any]] = {}
        self._cdp_main_frames: dict[int, str] = {}
        self._cdp_tasks: set[asyncio.Task[None]] = set()
        self._bound_events: list[dict[str, Any]] = []

    async def start(self) -> dict[str, Any]:
        context = self.browser._context
        if not self._binding_registered and hasattr(context, "expose_binding"):
            await context.expose_binding(
                "__autoflowRecordEvent", self._capture_bound_event
            )
            self._binding_registered = True
        if not self._cdp_registered and hasattr(context, "on"):
            context.on("page", self._schedule_cdp_page)
            self._cdp_registered = True
        for page in context.pages:
            await self._register_cdp_page(page)
        if not self._registered:
            await context.add_init_script(RECORDER_SCRIPT)
            self._registered = True
        await context.add_init_script("window.__webrpaRecorderDisabled = false;")
        for page in context.pages:
            for frame in _frames(page):
                with suppress(Exception):
                    await frame.evaluate(
                        "() => { window.__webrpaRecorderDisabled = false; "
                        "try { sessionStorage.setItem('__webrpa_rec','[]'); } catch(e){} }"
                    )
        self.active = True
        for page in context.pages:
            for frame in _frames(page):
                with suppress(Exception):
                    await frame.evaluate(RECORDER_SCRIPT)
        return {"recording": True, "events": []}

    async def events(self) -> dict[str, Any]:
        return {
            "recording": self.active,
            "events": await self._drain() if self.active else [],
        }

    async def stop(self) -> dict[str, Any]:
        events = await self._drain() if self.active else []
        context = self.browser._context
        for page in context.pages:
            for frame in _frames(page):
                with suppress(Exception):
                    await frame.evaluate(
                        "() => { window.__webrpaRecorderDisabled = true; "
                        "var b=document.getElementById('__webrpa_rec_badge'); if(b)b.remove(); }"
                    )
        with suppress(Exception):
            await context.add_init_script("window.__webrpaRecorderDisabled = true;")
        self.active = False
        return {"recording": False, "events": events}

    def _schedule_cdp_page(self, page: Any) -> None:
        task = asyncio.create_task(self._register_cdp_page(page))
        self._cdp_tasks.add(task)
        task.add_done_callback(self._cdp_tasks.discard)

    async def _register_cdp_page(self, page: Any) -> None:
        page_key = id(page)
        context = self.browser._context
        if page_key in self._cdp_sessions or not hasattr(context, "new_cdp_session"):
            return
        try:
            session = await context.new_cdp_session(page)
            self._cdp_sessions[page_key] = session
            session.on(
                "Runtime.executionContextCreated",
                lambda event: self._schedule_cdp_context(page, session, event),
            )
            session.on(
                "Runtime.bindingCalled",
                lambda event: self._capture_cdp_event(page, event),
            )
            await session.send("Runtime.enable")
            frame_tree = await session.send("Page.getFrameTree")
            self._cdp_main_frames[page_key] = str(
                frame_tree.get("frameTree", {}).get("frame", {}).get("id", "")
            )
            await session.send(
                "Runtime.addBinding", {"name": "__autoflowRecordCdp"}
            )
        except Exception:  # noqa: BLE001 -- sessionStorage remains the fallback.
            self._cdp_sessions.pop(page_key, None)

    def _schedule_cdp_context(
        self, page: Any, session: Any, event: dict[str, Any]
    ) -> None:
        context = event.get("context", {})
        context_id = context.get("id")
        if not isinstance(context_id, int):
            return
        self._cdp_contexts[(id(page), context_id)] = context.get("auxData", {})

        async def bind() -> None:
            with suppress(Exception):
                await session.send(
                    "Runtime.addBinding",
                    {
                        "name": "__autoflowRecordCdp",
                        "executionContextId": context_id,
                    },
                )

        task = asyncio.create_task(bind())
        self._cdp_tasks.add(task)
        task.add_done_callback(self._cdp_tasks.discard)

    def _capture_cdp_event(self, page: Any, message: dict[str, Any]) -> None:
        if not self.active:
            return
        if message.get("name") != "__autoflowRecordCdp":
            return
        try:
            event = json.loads(message.get("payload", ""))
        except (TypeError, ValueError):
            return
        if not isinstance(event, dict):
            return
        page_key = id(page)
        context_id = message.get("executionContextId")
        context = (
            self._cdp_contexts.get((page_key, context_id), {})
            if isinstance(context_id, int)
            else {}
        )
        frame_id = str(context.get("frameId", ""))
        frame_meta: dict[str, Any] = {
            "main": not frame_id or frame_id == self._cdp_main_frames.get(page_key, "")
        }
        if not frame_meta["main"]:
            main_frame = getattr(page, "main_frame", None)
            child_frames = [frame for frame in _frames(page) if frame is not main_frame]
            frame_meta.update({"index": -1, "name": "", "selector": ""})
            event_url = event.get("url", "")
            for index, frame in enumerate(child_frames):
                if getattr(frame, "url", "") == event_url:
                    frame_meta["index"] = index
                    with suppress(Exception):
                        frame_meta["name"] = frame.name or ""
                    break
        self._bound_events.append({**event, "_frame": frame_meta})

    async def _drain(self) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for page in self.browser._context.pages:
            frames = _frames(page)
            child_frames = [frame for frame in frames if frame is not page.main_frame]
            for frame in frames:
                with suppress(Exception):
                    values = await frame.evaluate(_DRAIN_JS)
                    if not isinstance(values, list):
                        continue
                    frame_meta = await _frame_meta(page, frame, child_frames)
                    for value in values:
                        if isinstance(value, dict):
                            merged.append({**value, "_frame": frame_meta})
        await asyncio.sleep(0)
        merged.extend(self._bound_events)
        self._bound_events = []
        return _merge_events(merged)

    async def _capture_bound_event(
        self, source: dict[str, Any], event: object
    ) -> None:
        if not self.active or not isinstance(event, dict):
            return
        page = source.get("page")
        frame = source.get("frame")
        if page is None or frame is None:
            return
        try:
            frames = _frames(page)
            frame_meta = await _frame_meta(
                page, frame, [item for item in frames if item is not page.main_frame]
            )
        except Exception:  # noqa: BLE001 -- a navigation may detach the source frame.
            frame_meta = {"main": frame is getattr(page, "main_frame", None)}
        self._bound_events.append({**event, "_frame": frame_meta})


def _frames(page: Any) -> list[Any]:
    try:
        return list(page.frames)
    except Exception:  # noqa: BLE001 -- browser wrappers expose varying page types.
        return [page]


async def _frame_meta(page: Any, frame: Any, child_frames: list[Any]) -> dict[str, Any]:
    if frame is page.main_frame:
        return {"main": True}
    meta: dict[str, Any] = {"main": False, "index": -1, "name": "", "selector": ""}
    with suppress(ValueError):
        meta["index"] = child_frames.index(frame)
    with suppress(Exception):
        meta["name"] = frame.name or ""
    direct = False
    with suppress(Exception):
        direct = frame.parent_frame is page.main_frame
    with suppress(Exception):
        element = await frame.frame_element()
        frame_id = await element.get_attribute("id")
        name = await element.get_attribute("name")
        src = await element.get_attribute("src")
        if direct:
            if frame_id and re.match(r"^[A-Za-z][\w-]*$", frame_id):
                meta["selector"] = "iframe#" + frame_id
            elif name:
                escaped_name = name.replace('"', '\\"')
                meta["selector"] = f'iframe[name="{escaped_name}"]'
            elif src and len(src) <= 200:
                escaped_src = src.replace('"', '\\"')
                meta["selector"] = f'iframe[src="{escaped_src}"]'
        if not meta["name"]:
            meta["name"] = name or frame_id or ""
    return meta


def _merge_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(events, key=lambda event: event.get("ts", 0))
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for original in ordered:
        event_id = original.get("__autoflowRecordId")
        if isinstance(event_id, str):
            if event_id in seen:
                continue
            seen.add(event_id)
        event = {
            key: value
            for key, value in original.items()
            if key != "__autoflowRecordId"
        }
        previous = merged[-1] if merged else None
        same_target = bool(
            previous
            and previous.get("selector") == event.get("selector")
            and previous.get("_frame") == event.get("_frame")
        )
        if event.get("type") == "input" and previous and same_target:
            merged[-1] = event
        elif event.get("type") == "scroll" and previous and same_target and (
            (float(previous.get("dy", 0)) > 0) == (float(event.get("dy", 0)) > 0)
        ):
            previous["dy"] = float(previous.get("dy", 0)) + float(
                event.get("dy", 0)
            )
            previous["y"] = event.get("y")
            previous["ts"] = event.get("ts")
        elif event.get("type") == "dblclick":
            removed = 0
            while merged and removed < 2:
                previous = merged[-1]
                if (
                    previous.get("type") == "click"
                    and previous.get("selector") == event.get("selector")
                    and previous.get("_frame") == event.get("_frame")
                ):
                    merged.pop()
                    removed += 1
                else:
                    break
            merged.append(event)
        elif (
            event.get("type") == "navigate"
            and previous
            and previous.get("type") == "navigate"
            and previous.get("url") == event.get("url")
            and previous.get("_frame") == event.get("_frame")
        ):
            continue
        else:
            merged.append(event)
    return merged
