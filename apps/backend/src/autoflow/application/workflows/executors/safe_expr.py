"""安全表达式求值器（用于工作流循环/条件表达式）。

背景：此前用 eval(expr, {"__builtins__": {}}, vars) 求值条件，虽隔离了 builtins，
但 Python 该沙箱存在已知逃逸手法（如 ().__class__.__base__.__subclasses__()），
从工作流仓库导入他人分享的工作流时，恶意条件表达式可能借此执行任意代码。

本模块用 AST 白名单求值：仅允许 比较 / 布尔运算 / 一元与二元算术 / 成员运算 /
字面量 / 变量引用，禁止属性访问（杜绝 __class__ 等 dunder）、函数调用、下标以外的
任何可调用/导入行为。无法安全求值时抛出 UnsafeExpressionError，由调用方回退处理。
"""

from __future__ import annotations

# Source: reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb,
# backend/app/utils/safe_expr.py.
import ast
import operator
import re
from typing import Any

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# 幂运算上限，防止 10**10**10 之类的资源耗尽
_MAX_POW_EXP = 1000
_MAX_AST_NODES = 256
_MAX_TEXT_CHARS = 1_048_576
_MAX_COLLECTION_ITEMS = 100_000
_MAX_INTEGER_BITS = 14_000

_CREDENTIAL_REFERENCE = re.compile(
    r"\{\{\s*(?:cred|凭据)\s*[:：]\s*[^{}]+?\s*\}\}"
)

# 允许的内置函数（数据处理常用，均无副作用/无法逃逸）
_SAFE_FUNCS: dict[str, Any] = {
    "len": len,
    "abs": abs,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "any": any,
    "all": all,
}

# 允许在值上调用的方法名（字符串/列表/字典常用；一律不含下划线，杜绝 dunder）
_SAFE_METHODS = frozenset(
    {
        "startswith",
        "endswith",
        "lower",
        "upper",
        "strip",
        "lstrip",
        "rstrip",
        "split",
        "rsplit",
        "replace",
        "find",
        "rfind",
        "count",
        "isdigit",
        "isalpha",
        "isalnum",
        "isspace",
        "title",
        "capitalize",
        "join",
        "get",
        "keys",
        "values",
        "items",
        "index",
    }
)


class UnsafeExpressionError(Exception):
    """表达式包含不允许的语法（属性访问/函数调用/导入等）或无法安全求值。"""


def safe_eval(expr: str, variables: dict[str, Any] | None = None) -> Any:
    """安全求值一个表达式字符串。variables 提供可引用的变量。

    仅支持比较/布尔/算术/成员运算与字面量、变量引用；遇到任何不在白名单内的
    语法节点或未知变量都会抛出 UnsafeExpressionError。
    """
    variables = variables or {}
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:  # 语法错误交给调用方回退
        raise UnsafeExpressionError(f"表达式语法错误: {e}")
    if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
        raise UnsafeExpressionError("表达式结构超过工作流安全限制")
    return _eval(tree.body, variables)


def format_expression_error(prefix: str, error: Exception, source: Any) -> str:
    """Keep resolved credential values out of workflow events and logs."""
    if isinstance(source, str) and _CREDENTIAL_REFERENCE.search(source):
        return prefix
    return f"{prefix}: {error!s}"


def _sequence_limit(value: Any) -> tuple[int, int] | None:
    if isinstance(value, str):
        return len(value), _MAX_TEXT_CHARS
    if isinstance(value, (list, tuple, set)):
        return len(value), _MAX_COLLECTION_ITEMS
    return None


def _bounded(value: Any) -> Any:
    limit = _sequence_limit(value)
    if limit is not None and limit[0] > limit[1]:
        kind = "文本" if isinstance(value, str) else "集合"
        raise UnsafeExpressionError(f"表达式{kind}结果超过工作流安全限制")
    if isinstance(value, dict) and len(value) > _MAX_COLLECTION_ITEMS:
        raise UnsafeExpressionError("表达式集合结果超过工作流安全限制")
    if isinstance(value, int) and value.bit_length() > _MAX_INTEGER_BITS:
        raise UnsafeExpressionError("表达式整数结果超过工作流安全限制")
    return value


def _guard_binary_result(node: ast.BinOp, left: Any, right: Any) -> None:
    if isinstance(node.op, ast.Mult):
        sequence, repeat = (left, right) if isinstance(right, int) else (right, left)
        limit = _sequence_limit(sequence)
        if limit is not None and isinstance(repeat, int):
            size, maximum = limit
            if size * max(repeat, 0) > maximum:
                kind = "文本" if isinstance(sequence, str) else "集合"
                raise UnsafeExpressionError(
                    f"表达式{kind}结果超过工作流安全限制"
                )
    elif isinstance(node.op, ast.Add):
        left_limit = _sequence_limit(left)
        right_limit = _sequence_limit(right)
        if left_limit is not None and right_limit is not None:
            maximum = min(left_limit[1], right_limit[1])
            if left_limit[0] + right_limit[0] > maximum:
                kind = "文本" if isinstance(left, str) else "集合"
                raise UnsafeExpressionError(
                    f"表达式{kind}结果超过工作流安全限制"
                )
    if (
        isinstance(node.op, ast.Pow)
        and isinstance(left, int)
        and isinstance(right, int)
        and right > 0
        and left not in {-1, 0, 1}
    ):
        estimated_bits = max(left.bit_length() - 1, 1) * right + 1
        if estimated_bits > _MAX_INTEGER_BITS:
            raise UnsafeExpressionError("表达式整数结果超过工作流安全限制")


def _guard_method_call(method: str, obj: Any, args: list[Any]) -> None:
    _bounded(obj)
    for argument in args:
        _bounded(argument)
    if method == "replace" and isinstance(obj, str) and len(args) in {2, 3}:
        old, new = args[0], args[1]
        if isinstance(old, str) and isinstance(new, str):
            occurrences = obj.count(old)
            if len(args) == 3 and isinstance(args[2], int) and args[2] >= 0:
                occurrences = min(occurrences, args[2])
            estimated_chars = len(obj) + occurrences * (len(new) - len(old))
            if estimated_chars > _MAX_TEXT_CHARS:
                raise UnsafeExpressionError(
                    "表达式文本结果超过工作流安全限制"
                )
    if method == "join" and isinstance(obj, str) and len(args) == 1:
        values = args[0]
        if isinstance(values, (list, tuple)) and all(
            isinstance(value, str) for value in values
        ):
            estimated_chars = sum(len(value) for value in values)
            estimated_chars += len(obj) * max(len(values) - 1, 0)
            if estimated_chars > _MAX_TEXT_CHARS:
                raise UnsafeExpressionError(
                    "表达式文本结果超过工作流安全限制"
                )


def _eval(node: ast.AST, vars: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return _bounded(node.value)

    if isinstance(node, ast.Name):
        if node.id in vars:
            return _bounded(vars[node.id])
        raise UnsafeExpressionError(f"未知变量: {node.id}")

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: Any = True
            for v in node.values:
                result = _eval(v, vars)
                if not result:
                    return result
            return result
        # Or
        result = False
        for v in node.values:
            result = _eval(v, vars)
            if result:
                return result
        return result

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _bounded(
            _UNARY_OPS[type(node.op)](_eval(node.operand, vars))  # type: ignore[operator]
        )

    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval(node.left, vars)
        right = _eval(node.right, vars)
        if isinstance(node.op, ast.Pow):
            try:
                if isinstance(right, (int, float)) and right > _MAX_POW_EXP:
                    raise UnsafeExpressionError("幂运算指数过大")
            except TypeError:
                pass
        _guard_binary_result(node, left, right)
        return _bounded(_BIN_OPS[type(node.op)](left, right))

    if isinstance(node, ast.Compare):
        left = _eval(node.left, vars)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _CMP_OPS:
                raise UnsafeExpressionError(f"不支持的比较运算: {op_type.__name__}")
            right = _eval(comparator, vars)
            if not _CMP_OPS[op_type](left, right):
                return False
            left = right
        return True

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        items = [_eval(e, vars) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return _bounded(tuple(items))
        if isinstance(node, ast.Set):
            return _bounded(set(items))
        return _bounded(items)

    if isinstance(node, ast.Dict):
        return _bounded(
            {
                _eval(k, vars): _eval(v, vars)  # type: ignore[arg-type]
                for k, v in zip(node.keys, node.values)
            }
        )

    # 受限函数调用：仅允许 白名单内置函数 或 值上的白名单方法（方法名不得含下划线）
    if isinstance(node, ast.Call):
        if getattr(node, "keywords", None):
            raise UnsafeExpressionError("不允许关键字参数")
        args = [_eval(a, vars) for a in node.args]
        func_node = node.func
        if isinstance(func_node, ast.Name):
            fn = _SAFE_FUNCS.get(func_node.id)
            if fn is None:
                raise UnsafeExpressionError(f"不允许的函数: {func_node.id}")
            for argument in args:
                _bounded(argument)
            return _bounded(fn(*args))
        if isinstance(func_node, ast.Attribute):
            attr = func_node.attr
            if attr.startswith("_") or attr not in _SAFE_METHODS:
                raise UnsafeExpressionError(f"不允许的方法: {attr}")
            obj = _eval(func_node.value, vars)
            method = getattr(obj, attr, None)
            if not callable(method):
                raise UnsafeExpressionError(f"不可调用的方法: {attr}")
            _guard_method_call(attr, obj, args)
            return _bounded(method(*args))
        raise UnsafeExpressionError("不允许的调用形式")

    # 属性访问：仅在“方法调用”里通过上面的 ast.Call 分支处理；
    # 独立的属性访问（尤其 __class__ 等 dunder）一律拒绝，杜绝沙箱逃逸。
    # 其余节点（Lambda / Comprehension / Subscript / Starred 等）一律拒绝
    raise UnsafeExpressionError(f"不允许的表达式节点: {type(node).__name__}")
