"""WebRPA AI task executors adapted to AutoFlow managed model IDs.

Source: reference/WebRPA/backend/app/executors/ai_tasks.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: provider connection fields use the main application's model boundary.
"""

from __future__ import annotations

import json
import re
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .ai import invoke_managed_chat
from .base import ModuleExecutor, ModuleResult
from .type_utils import to_int


class _AITaskExecutor(ModuleExecutor):
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(config.get("modelId"), str) or not config["modelId"].strip():
            return False, "请选择主应用中的模型"
        return True, ""


async def _chat(
    config: dict[str, Any],
    context: ExecutionContext,
    system_prompt: str,
    user_prompt: str,
) -> tuple[bool, str, str]:
    try:
        result, _model_id = await invoke_managed_chat(
            config,
            context,
            system_prompt,
            user_prompt,
            default_temperature=0.2,
        )
    except Exception as error:  # noqa: BLE001 - provider errors become node errors.
        return False, "", str(error) or "模型调用失败"
    return True, result.content.strip(), ""


def _extract_json(text: str) -> Any:
    """从模型返回里健壮地抽取 JSON（兼容 ```json 代码块、前后多余文字）。"""
    if not text:
        return None
    s = text.strip()
    # 去掉 ```json ... ``` 围栏
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if fence:
        s = fence.group(1).strip()
    # 直接尝试
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # 截取第一个 { 或 [ 到最后一个 } 或 ]
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        i = s.find(open_ch)
        j = s.rfind(close_ch)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except json.JSONDecodeError:
                continue
    return None


class AIExtractExecutor(_AITaskExecutor):
    """AI 结构化抽取：从任意文本中按指定字段抽取为 JSON 对象"""

    @property
    def module_type(self) -> str:
        return "ai_extract"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        text = context.resolve_value(config.get("inputText", ""))
        fields_raw = context.resolve_value(config.get("fields", ""))
        var = config.get("variableName", "") or config.get("resultVariable", "")
        if not text or not str(text).strip():
            return ModuleResult(success=False, error="待抽取文本(inputText)不能为空")
        if not fields_raw or not str(fields_raw).strip():
            return ModuleResult(success=False, error="请填写要抽取的字段(fields)，如 姓名,电话,地址 或 JSON 描述")
        # 字段可以是逗号分隔，也可以是 JSON（字段名->说明）
        fields_desc = str(fields_raw).strip()
        sys_p = (
            "你是一个严谨的信息抽取引擎。请从用户提供的文本中抽取指定字段，"
            "只输出一个 JSON 对象，键为字段名，值为抽取到的内容；"
            "找不到的字段值用空字符串 \"\"。不要输出任何解释、不要用代码块包裹。"
        )
        user_p = f"【要抽取的字段】\n{fields_desc}\n\n【原始文本】\n{text}"
        ok, content, err = await _chat(config, context, sys_p, user_p)
        if not ok:
            return ModuleResult(success=False, error=err)
        data = _extract_json(content)
        if data is None:
            # 兜底：把原始文本存入变量
            if var:
                context.set_variable(var, content)
            return ModuleResult(success=True, message="已抽取（未解析为JSON，返回原始文本）",
                                data={"raw": content})
        if var:
            context.set_variable(var, data)
        return ModuleResult(success=True, message=f"已抽取 {len(data) if isinstance(data, dict) else ''} 个字段",
                            data={"result": data})


class AIClassifyExecutor(_AITaskExecutor):
    """AI 文本分类：把文本归入给定类别之一"""

    @property
    def module_type(self) -> str:
        return "ai_classify"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        text = context.resolve_value(config.get("inputText", ""))
        categories_raw = context.resolve_value(config.get("categories", ""))
        var = config.get("variableName", "") or config.get("resultVariable", "")
        if not text or not str(text).strip():
            return ModuleResult(success=False, error="待分类文本(inputText)不能为空")
        cats = [c.strip() for c in str(categories_raw).replace("，", ",").split(",") if c.strip()]
        if len(cats) < 2:
            return ModuleResult(success=False, error="请提供至少两个类别(categories)，逗号分隔")
        sys_p = (
            "你是一个精准的文本分类器。请把文本归入给定类别中最贴切的一个，"
            "只输出 JSON：{\"category\":\"类别名\",\"confidence\":0~1,\"reason\":\"简短理由\"}。"
            "category 必须严格是给定类别之一，不要新造类别，不要用代码块包裹。"
        )
        user_p = f"【可选类别】{', '.join(cats)}\n\n【文本】\n{text}"
        ok, content, err = await _chat(config, context, sys_p, user_p)
        if not ok:
            return ModuleResult(success=False, error=err)
        data = _extract_json(content)
        category = ""
        if isinstance(data, dict):
            category = str(data.get("category", "")).strip()
        if category not in cats:
            # 兜底：在返回里找哪个类别名出现了
            for c in cats:
                if c in content:
                    category = c
                    break
        if var:
            context.set_variable(var, category or (data if data else content))
        return ModuleResult(success=True, message=f"分类结果: {category or '未识别'}",
                            data={"category": category, "detail": data})


class AISummarizeExecutor(_AITaskExecutor):
    """AI 文本摘要：把长文本压缩成摘要（可指定字数与风格）"""

    @property
    def module_type(self) -> str:
        return "ai_summarize"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        text = context.resolve_value(config.get("inputText", ""))
        max_words = to_int(config.get("maxWords", 200), 200, context)
        style = context.resolve_value(config.get("style", "")) or ""
        var = config.get("variableName", "") or config.get("resultVariable", "")
        if not text or not str(text).strip():
            return ModuleResult(success=False, error="待摘要文本(inputText)不能为空")
        style_hint = f"风格要求：{style}。" if style else ""
        sys_p = (
            f"你是一个专业的摘要助手。请用中文把文本浓缩成不超过 {max_words} 字的摘要，"
            f"保留关键信息与结论，去掉冗余。{style_hint}只输出摘要正文，不要前缀、不要解释。"
        )
        ok, content, err = await _chat(config, context, sys_p, str(text))
        if not ok:
            return ModuleResult(success=False, error=err)
        if var:
            context.set_variable(var, content)
        disp = content[:100] + "…" if len(content) > 100 else content
        return ModuleResult(success=True, message=f"摘要: {disp}", data={"summary": content})


class AITranslateExecutor(_AITaskExecutor):
    """AI 翻译：把文本翻译成目标语言"""

    @property
    def module_type(self) -> str:
        return "ai_translate"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        text = context.resolve_value(config.get("inputText", ""))
        target_lang = context.resolve_value(config.get("targetLang", "英文")) or "英文"
        var = config.get("variableName", "") or config.get("resultVariable", "")
        if not text or not str(text).strip():
            return ModuleResult(success=False, error="待翻译文本(inputText)不能为空")
        sys_p = (
            f"你是一个专业翻译。请把用户文本准确、地道地翻译成{target_lang}，"
            "保留原文的格式与换行。只输出译文，不要原文、不要解释、不要拼音。"
        )
        ok, content, err = await _chat(config, context, sys_p, str(text))
        if not ok:
            return ModuleResult(success=False, error=err)
        if var:
            context.set_variable(var, content)
        disp = content[:100] + "…" if len(content) > 100 else content
        return ModuleResult(success=True, message=f"译文: {disp}", data={"translation": content, "targetLang": target_lang})


class AISentimentExecutor(_AITaskExecutor):
    """AI 情感分析：判断文本情感倾向（正面/负面/中性）"""

    @property
    def module_type(self) -> str:
        return "ai_sentiment"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        text = context.resolve_value(config.get("inputText", ""))
        var = config.get("variableName", "") or config.get("resultVariable", "")
        if not text or not str(text).strip():
            return ModuleResult(success=False, error="待分析文本(inputText)不能为空")
        sys_p = (
            "你是情感分析引擎。判断文本的情感倾向，只输出 JSON："
            "{\"sentiment\":\"正面|负面|中性\",\"score\":-1~1,\"confidence\":0~1,\"reason\":\"简短理由\"}。"
            "score 越接近 1 越正面，越接近 -1 越负面。不要用代码块包裹。"
        )
        ok, content, err = await _chat(config, context, sys_p, str(text))
        if not ok:
            return ModuleResult(success=False, error=err)
        data = _extract_json(content)
        sentiment = ""
        if isinstance(data, dict):
            sentiment = str(data.get("sentiment", "")).strip()
        if not sentiment:
            for s in ("正面", "负面", "中性"):
                if s in content:
                    sentiment = s
                    break
        if var:
            context.set_variable(var, data if data else {"sentiment": sentiment, "raw": content})
        return ModuleResult(success=True, message=f"情感: {sentiment or '未识别'}",
                            data={"sentiment": sentiment, "detail": data})


# ============================================================
# 数据清洗 / 规整 / 语义去重 / 智能路由
# ============================================================

_NORMALIZE_RULES = {
    "date": "把日期/时间统一为标准格式 YYYY-MM-DD（含时间则 YYYY-MM-DD HH:mm:ss）。识别各种写法：'2024年3月5日'、'3/5/24'、'昨天'(相对今天)、'March 5 2024' 等。",
    "money": "把金额统一为纯数字（不带货币符号/千分位/单位），如 '￥1,299.00'→1299，'2.5万'→25000，'$3.2k'→3200。",
    "phone": "把电话号码统一为纯数字标准格式（中国手机号 11 位；带区号座机保留区号，用 - 连接），去掉空格/括号/+86。",
    "number": "把文本里的数值统一为纯数字（去单位/千分位），中文数字也要转阿拉伯数字。",
    "name": "规整人名：去掉多余空格与称谓（先生/女士/老师等），保留姓名本体。",
    "address": "规整地址：补全省市区层级、去除冗余空格，输出规范地址字符串。",
}


class AINormalizeExecutor(_AITaskExecutor):
    """AI 数据规整：把杂乱的日期/金额/电话/数值/地址等统一成标准格式"""

    @property
    def module_type(self) -> str:
        return "ai_normalize"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        text = context.resolve_value(config.get("inputText", ""))
        ntype = (context.resolve_value(config.get("normalizeType", "date")) or "date").strip()
        target_format = context.resolve_value(config.get("targetFormat", "")) or ""
        var = config.get("variableName", "") or config.get("resultVariable", "")
        if text is None or str(text).strip() == "":
            return ModuleResult(success=False, error="待规整内容(inputText)不能为空")
        rule = _NORMALIZE_RULES.get(ntype)
        if not rule and not target_format:
            return ModuleResult(success=False, error=f"未知规整类型: {ntype}（可选 date/money/phone/number/name/address，或填 targetFormat 自定义）")
        rule_text = rule or f"按以下目标格式规整：{target_format}"
        if target_format and rule:
            rule_text += f" 目标格式：{target_format}。"
        sys_p = (
            "你是一个数据规整引擎。" + rule_text +
            " 只输出规整后的结果本身，不要任何解释、引号、单位或多余字符。"
            "如果输入本身无法识别，原样返回输入。"
        )
        ok, content, err = await _chat(config, context, sys_p, str(text))
        if not ok:
            return ModuleResult(success=False, error=err)
        result = content.strip().strip('"').strip("'")
        if var:
            context.set_variable(var, result)
        return ModuleResult(success=True, message=f"规整结果: {result}", data={"result": result, "type": ntype})


class AIDedupSemanticExecutor(_AITaskExecutor):
    """AI 语义去重：对列表做语义层面的去重（合并表达不同但含义相同的项）"""

    @property
    def module_type(self) -> str:
        return "ai_dedup_semantic"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        raw = context.resolve_value(config.get("inputList", ""))
        var = config.get("variableName", "") or config.get("resultVariable", "")
        # 解析为列表
        items: list
        if isinstance(raw, (list, tuple)):
            items = list(raw)
        else:
            s = str(raw or "").strip()
            if not s:
                return ModuleResult(success=False, error="待去重列表(inputList)不能为空")
            try:
                parsed = json.loads(s)
                items = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                items = [x.strip() for x in s.replace("，", ",").split(",") if x.strip()]
        if not items:
            return ModuleResult(success=False, error="列表为空")
        if len(items) > 300:
            return ModuleResult(success=False, error=f"列表过长({len(items)}项)，语义去重建议 ≤300 项；可先分批")
        # 给每项编号，让模型只返回保留项的编号，避免改写内容
        numbered = "\n".join(f"{i}. {json.dumps(it, ensure_ascii=False) if not isinstance(it, str) else it}" for i, it in enumerate(items))
        sys_p = (
            "你是语义去重引擎。下面是带编号的列表项，请找出语义上重复（表达不同但含义相同）的项，"
            "每组重复只保留第一个出现的编号。只输出一个 JSON 数组，元素是要【保留】的项的编号（整数），"
            "按原顺序排列。不要输出解释、不要用代码块包裹。"
        )
        ok, content, err = await _chat(config, context, sys_p, numbered)
        if not ok:
            return ModuleResult(success=False, error=err)
        keep = _extract_json(content)
        if not isinstance(keep, list):
            # 兜底：返回原列表
            if var:
                context.set_variable(var, items)
            return ModuleResult(success=True, message="未能解析去重结果，返回原列表", data={"result": items})
        seen = set()
        result = []
        for idx in keep:
            try:
                i = int(idx)
            except (TypeError, ValueError, OverflowError):
                continue
            if 0 <= i < len(items) and i not in seen:
                seen.add(i)
                result.append(items[i])
        if not result:
            result = items
        if var:
            context.set_variable(var, result)
        removed = len(items) - len(result)
        return ModuleResult(success=True, message=f"语义去重：{len(items)} → {len(result)}（去掉 {removed} 项）",
                            data={"result": result, "removed": removed})


class AIRouteExecutor(_AITaskExecutor):
    """AI 智能路由：根据输入内容从给定分支中选择最合适的一个，输出分支名（配合条件分支使用）"""

    @property
    def module_type(self) -> str:
        return "ai_route"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        text = context.resolve_value(config.get("inputText", ""))
        routes_raw = context.resolve_value(config.get("routes", ""))
        var = config.get("variableName", "") or config.get("resultVariable", "")
        if text is None or str(text).strip() == "":
            return ModuleResult(success=False, error="待判断内容(inputText)不能为空")
        # routes 支持：JSON {名称:说明} / "名称:说明" 多行 / 逗号分隔名称
        routes: dict[str, str] = {}
        rs = str(routes_raw or "").strip()
        parsed = None
        try:
            parsed = json.loads(rs)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            routes = {str(k): str(v) for k, v in parsed.items()}
        elif isinstance(parsed, list):
            routes = {str(x): "" for x in parsed}
        else:
            # 分隔符优先用 分号/换行（描述里常含逗号，不能用逗号拆），都没有时才用逗号
            norm = rs.replace("；", ";").replace("\n", ";")
            parts = norm.split(";") if (";" in norm) else norm.replace("，", ",").split(",")
            for line in parts:
                line = line.strip()
                if not line:
                    continue
                if ":" in line or "：" in line:
                    name, _, desc = line.replace("：", ":").partition(":")
                    routes[name.strip()] = desc.strip()
                else:
                    routes[line] = ""
        if len(routes) < 2:
            return ModuleResult(success=False, error="请提供至少两个分支(routes)，如 退款:要求退钱; 咨询:询问信息; 投诉:表达不满")
        names = list(routes.keys())
        route_desc = "\n".join(f"- {n}：{d or '（无说明）'}" for n, d in routes.items())
        sys_p = (
            "你是一个智能路由决策器。根据用户内容，从给定分支中选出最贴切的一个，"
            "只输出 JSON：{\"route\":\"分支名\",\"confidence\":0~1,\"reason\":\"简短理由\"}。"
            "route 必须严格是给定分支名之一，不要新造。不要用代码块包裹。"
        )
        user_p = f"【可选分支】\n{route_desc}\n\n【用户内容】\n{text}"
        ok, content, err = await _chat(config, context, sys_p, user_p)
        if not ok:
            return ModuleResult(success=False, error=err)
        data = _extract_json(content)
        chosen = ""
        if isinstance(data, dict):
            chosen = str(data.get("route", "")).strip()
        if chosen not in routes:
            for n in names:
                if n in content:
                    chosen = n
                    break
        if chosen not in routes:
            chosen = names[0]
        if var:
            context.set_variable(var, chosen)
        return ModuleResult(success=True, message=f"路由 → {chosen}",
                            data={"route": chosen, "detail": data, "routes": names})

AI_TASK_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    AIExtractExecutor,
    AIClassifyExecutor,
    AISummarizeExecutor,
    AITranslateExecutor,
    AISentimentExecutor,
    AINormalizeExecutor,
    AIDedupSemanticExecutor,
    AIRouteExecutor,
)
