"""Approved frozen WebRPA utility executors for AutoFlow workflows.

Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
backend/app/executors/utility_tools.py. File-comparison and printer nodes from that
source module are outside the approved Studio scope and are intentionally absent.
"""

from __future__ import annotations

# ruff: noqa: BLE001, DTZ005, DTZ006, DTZ007 -- preserve frozen result/time semantics.
import hashlib
import secrets
import string
import urllib.parse
import uuid
from datetime import datetime

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_float, to_int


class RandomPasswordGeneratorExecutor(ModuleExecutor):
    """随机密码生成模块执行器"""

    @property
    def module_type(self) -> str:
        return "random_password_generator"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        length = to_int(config.get("length", 16), 16, context)
        include_uppercase_raw = config.get("includeUppercase", True)
        if isinstance(include_uppercase_raw, str):
            include_uppercase_raw = context.resolve_value(include_uppercase_raw)
        include_uppercase = include_uppercase_raw in [True, "true", "True", "1", 1]

        include_lowercase_raw = config.get("includeLowercase", True)
        if isinstance(include_lowercase_raw, str):
            include_lowercase_raw = context.resolve_value(include_lowercase_raw)
        include_lowercase = include_lowercase_raw in [True, "true", "True", "1", 1]

        include_digits_raw = config.get("includeDigits", True)
        if isinstance(include_digits_raw, str):
            include_digits_raw = context.resolve_value(include_digits_raw)
        include_digits = include_digits_raw in [True, "true", "True", "1", 1]

        include_symbols_raw = config.get("includeSymbols", True)
        if isinstance(include_symbols_raw, str):
            include_symbols_raw = context.resolve_value(include_symbols_raw)
        include_symbols = include_symbols_raw in [True, "true", "True", "1", 1]

        exclude_ambiguous_raw = config.get("excludeAmbiguous", False)
        if isinstance(exclude_ambiguous_raw, str):
            exclude_ambiguous_raw = context.resolve_value(exclude_ambiguous_raw)
        exclude_ambiguous = exclude_ambiguous_raw in [True, "true", "True", "1", 1]

        # 默认变量名以前端 addNode 为准（random_password）
        result_variable = config.get("resultVariable", "random_password")

        try:
            # 构建字符集
            charset = ""
            if include_uppercase:
                charset += string.ascii_uppercase
            if include_lowercase:
                charset += string.ascii_lowercase
            if include_digits:
                charset += string.digits
            if include_symbols:
                charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"

            if not charset:
                return ModuleResult(success=False, error="至少需要选择一种字符类型")

            # 排除易混淆字符
            if exclude_ambiguous:
                ambiguous = "il1Lo0O"
                charset = "".join(c for c in charset if c not in ambiguous)

            # 生成密码
            password = "".join(secrets.choice(charset) for _ in range(length))

            if result_variable:
                context.set_variable(result_variable, password)

            return ModuleResult(
                success=True, message=f"已生成{length}位随机密码", data=password
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"密码生成失败: {e!s}")


class URLEncodeDecodeExecutor(ModuleExecutor):
    """URL编解码模块执行器"""

    @property
    def module_type(self) -> str:
        return "url_encode_decode"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        operation = context.resolve_value(config.get("operation", "encode"))
        encoding = context.resolve_value(config.get("encoding", "utf-8"))
        result_variable = config.get("resultVariable", "url_result")

        if not input_text:
            return ModuleResult(success=False, error="输入文本不能为空")

        try:
            if operation == "encode":
                result = urllib.parse.quote(input_text, safe="", encoding=encoding)
                msg = "URL编码完成"
            else:  # decode
                result = urllib.parse.unquote(input_text, encoding=encoding)
                msg = "URL解码完成"

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(success=True, message=msg, data=result)

        except Exception as e:
            return ModuleResult(success=False, error=f"URL编解码失败: {e!s}")


class MD5EncryptExecutor(ModuleExecutor):
    """MD5加密模块执行器"""

    @property
    def module_type(self) -> str:
        return "md5_encrypt"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        encoding = context.resolve_value(config.get("encoding", "utf-8"))
        output_format = context.resolve_value(config.get("outputFormat", "hex"))
        result_variable = config.get("resultVariable", "md5_hash")

        if not input_text:
            return ModuleResult(success=False, error="输入文本不能为空")

        try:
            md5_hash = hashlib.md5(input_text.encode(encoding))

            if output_format == "hex":
                result = md5_hash.hexdigest()
            else:  # base64
                import base64

                result = base64.b64encode(md5_hash.digest()).decode("ascii")

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(
                success=True, message=f"MD5加密完成 ({output_format}格式)", data=result
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"MD5加密失败: {e!s}")


class SHAEncryptExecutor(ModuleExecutor):
    """SHA加密模块执行器"""

    @property
    def module_type(self) -> str:
        return "sha_encrypt"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        input_text = context.resolve_value(config.get("inputText", ""))
        sha_type = context.resolve_value(config.get("shaType", "sha256"))
        encoding = context.resolve_value(config.get("encoding", "utf-8"))
        output_format = context.resolve_value(config.get("outputFormat", "hex"))
        result_variable = config.get("resultVariable", "sha_hash")

        if not input_text:
            return ModuleResult(success=False, error="输入文本不能为空")

        try:
            # 选择SHA算法
            hash_func = getattr(hashlib, sha_type.lower(), hashlib.sha256)
            sha_hash = hash_func(input_text.encode(encoding))

            if output_format == "hex":
                result = sha_hash.hexdigest()
            else:  # base64
                import base64

                result = base64.b64encode(sha_hash.digest()).decode("ascii")

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(
                success=True,
                message=f"{sha_type.upper()}加密完成 ({output_format}格式)",
                data=result,
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"SHA加密失败: {e!s}")


class TimestampConverterExecutor(ModuleExecutor):
    """时间戳转换器模块执行器"""

    @property
    def module_type(self) -> str:
        return "timestamp_converter"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        operation = context.resolve_value(config.get("operation", "to_timestamp"))
        input_value = context.resolve_value(config.get("inputValue", ""))
        timestamp_unit = context.resolve_value(config.get("timestampUnit", "seconds"))
        datetime_format = context.resolve_value(
            config.get("datetimeFormat", "%Y-%m-%d %H:%M:%S")
        )
        # 默认变量名以前端 addNode 为准（converted_time）
        result_variable = config.get("resultVariable", "converted_time")

        try:
            result: int | str
            if operation == "to_timestamp":
                # 日期时间转时间戳
                if not input_value:
                    # 如果没有输入，使用当前时间
                    dt = datetime.now()
                else:
                    dt = datetime.strptime(str(input_value), datetime_format)

                timestamp = dt.timestamp()
                if timestamp_unit == "milliseconds":
                    result = int(timestamp * 1000)
                else:
                    result = int(timestamp)

                msg = f"已转换为时间戳 ({timestamp_unit})"
            else:
                # 时间戳转日期时间
                if not input_value:
                    return ModuleResult(success=False, error="时间戳不能为空")

                # 修复：直接传递input_value而不是字典
                timestamp = to_float(input_value, 0, context)
                if timestamp == 0:
                    return ModuleResult(
                        success=False, error=f"无效的时间戳值: {input_value}"
                    )

                if timestamp_unit == "milliseconds":
                    timestamp = timestamp / 1000

                dt = datetime.fromtimestamp(timestamp)
                result = dt.strftime(datetime_format)
                msg = "已转换为日期时间"

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(success=True, message=msg, data=result)

        except Exception as e:
            return ModuleResult(success=False, error=f"时间戳转换失败: {e!s}")


class RGBToHSVExecutor(ModuleExecutor):
    """RGB转HSV模块执行器"""

    @property
    def module_type(self) -> str:
        return "rgb_to_hsv"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        r = to_int(config.get("r", 0), 0, context)
        g = to_int(config.get("g", 0), 0, context)
        b = to_int(config.get("b", 0), 0, context)
        result_variable = config.get("resultVariable", "hsv_color")

        try:
            import colorsys

            # RGB值范围0-255，需要归一化到0-1
            r_norm = r / 255.0
            g_norm = g / 255.0
            b_norm = b / 255.0

            # 转换为HSV
            h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)

            # HSV值转换为常用格式：H(0-360), S(0-100), V(0-100)
            h_deg = int(h * 360)
            s_pct = int(s * 100)
            v_pct = int(v * 100)

            result = {
                "h": h_deg,
                "s": s_pct,
                "v": v_pct,
                "string": f"HSV({h_deg}, {s_pct}%, {v_pct}%)",
            }

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(
                success=True,
                message=f"RGB({r},{g},{b}) → {result['string']}",
                data=result,
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"RGB转HSV失败: {e!s}")


class RGBToCMYKExecutor(ModuleExecutor):
    """RGB转CMYK模块执行器"""

    @property
    def module_type(self) -> str:
        return "rgb_to_cmyk"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        r = to_int(config.get("r", 0), 0, context)
        g = to_int(config.get("g", 0), 0, context)
        b = to_int(config.get("b", 0), 0, context)
        result_variable = config.get("resultVariable", "cmyk_color")

        try:
            # RGB值范围0-255，需要归一化到0-1
            r_norm = r / 255.0
            g_norm = g / 255.0
            b_norm = b / 255.0

            # 计算CMYK
            k = 1 - max(r_norm, g_norm, b_norm)

            if k == 1:
                c = m = y = 0.0
            else:
                c = (1 - r_norm - k) / (1 - k)
                m = (1 - g_norm - k) / (1 - k)
                y = (1 - b_norm - k) / (1 - k)

            # 转换为百分比
            c_pct = int(c * 100)
            m_pct = int(m * 100)
            y_pct = int(y * 100)
            k_pct = int(k * 100)

            result = {
                "c": c_pct,
                "m": m_pct,
                "y": y_pct,
                "k": k_pct,
                "string": f"CMYK({c_pct}%, {m_pct}%, {y_pct}%, {k_pct}%)",
            }

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(
                success=True,
                message=f"RGB({r},{g},{b}) → {result['string']}",
                data=result,
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"RGB转CMYK失败: {e!s}")


class HEXToCMYKExecutor(ModuleExecutor):
    """HEX转CMYK模块执行器"""

    @property
    def module_type(self) -> str:
        return "hex_to_cmyk"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        hex_color = context.resolve_value(config.get("hexColor", ""))
        result_variable = config.get("resultVariable", "cmyk_color")

        if not hex_color:
            return ModuleResult(success=False, error="HEX颜色值不能为空")

        try:
            # 移除#号
            hex_color = hex_color.lstrip("#")

            # 解析HEX颜色
            if len(hex_color) == 3:
                # 短格式 #RGB -> #RRGGBB
                hex_color = "".join([c * 2 for c in hex_color])

            if len(hex_color) != 6:
                return ModuleResult(success=False, error="无效的HEX颜色格式")

            # 转换为RGB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)

            # RGB归一化
            r_norm = r / 255.0
            g_norm = g / 255.0
            b_norm = b / 255.0

            # 计算CMYK
            k = 1 - max(r_norm, g_norm, b_norm)

            if k == 1:
                c = m = y = 0.0
            else:
                c = (1 - r_norm - k) / (1 - k)
                m = (1 - g_norm - k) / (1 - k)
                y = (1 - b_norm - k) / (1 - k)

            # 转换为百分比
            c_pct = int(c * 100)
            m_pct = int(m * 100)
            y_pct = int(y * 100)
            k_pct = int(k * 100)

            result = {
                "c": c_pct,
                "m": m_pct,
                "y": y_pct,
                "k": k_pct,
                "string": f"CMYK({c_pct}%, {m_pct}%, {y_pct}%, {k_pct}%)",
            }

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(
                success=True,
                message=f"#{hex_color.upper()} → {result['string']}",
                data=result,
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"HEX转CMYK失败: {e!s}")


class UUIDGeneratorExecutor(ModuleExecutor):
    """UUID生成器模块执行器"""

    @property
    def module_type(self) -> str:
        return "uuid_generator"

    async def execute(self, config: dict, context: ExecutionContext) -> ModuleResult:
        uuid_version = to_int(config.get("uuidVersion", 4), 4, context)
        uppercase_raw = config.get("uppercase", False)
        if isinstance(uppercase_raw, str):
            uppercase_raw = context.resolve_value(uppercase_raw)
        uppercase = uppercase_raw in [True, "true", "True", "1", 1]

        remove_hyphens_raw = config.get("removeHyphens", False)
        if isinstance(remove_hyphens_raw, str):
            remove_hyphens_raw = context.resolve_value(remove_hyphens_raw)
        remove_hyphens = remove_hyphens_raw in [True, "true", "True", "1", 1]

        # 默认变量名以前端 addNode 为准（uuid）
        result_variable = config.get("resultVariable", "uuid")

        try:
            # 生成UUID
            if uuid_version == 1:
                generated_uuid = uuid.uuid1()
            elif uuid_version == 3:
                namespace = context.resolve_value(config.get("namespace", ""))
                name = context.resolve_value(config.get("name", ""))
                if not namespace or not name:
                    return ModuleResult(
                        success=False, error="UUID v3需要namespace和name参数"
                    )
                ns = uuid.NAMESPACE_DNS if namespace == "dns" else uuid.NAMESPACE_URL
                generated_uuid = uuid.uuid3(ns, name)
            elif uuid_version == 5:
                namespace = context.resolve_value(config.get("namespace", ""))
                name = context.resolve_value(config.get("name", ""))
                if not namespace or not name:
                    return ModuleResult(
                        success=False, error="UUID v5需要namespace和name参数"
                    )
                ns = uuid.NAMESPACE_DNS if namespace == "dns" else uuid.NAMESPACE_URL
                generated_uuid = uuid.uuid5(ns, name)
            else:  # UUID v4 (默认)
                generated_uuid = uuid.uuid4()

            result = str(generated_uuid)

            if remove_hyphens:
                result = result.replace("-", "")

            if uppercase:
                result = result.upper()

            if result_variable:
                context.set_variable(result_variable, result)

            return ModuleResult(
                success=True, message=f"已生成UUID v{uuid_version}", data=result
            )

        except Exception as e:
            return ModuleResult(success=False, error=f"UUID生成失败: {e!s}")
