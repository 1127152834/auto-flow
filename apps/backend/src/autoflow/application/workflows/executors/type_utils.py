from __future__ import annotations

from typing import Any, Protocol


class ValueResolver(Protocol):
    def resolve_value(self, value: Any) -> Any: ...


def to_int(value: Any, default: int, context: ValueResolver | None = None) -> int:
    if value is None:
        return default
    if context is not None and isinstance(value, str):
        value = context.resolve_value(value)
    try:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            value = value.strip()
            return default if not value else int(float(value))
    except (ValueError, TypeError):
        pass
    return default


def to_float(value: Any, default: float, context: ValueResolver | None = None) -> float:
    if value is None:
        return default
    if context is not None and isinstance(value, str):
        value = context.resolve_value(value)
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            return default if not value else float(value)
    except (ValueError, TypeError):
        pass
    return default


def to_bool(
    value: Any, default: bool = False, context: ValueResolver | None = None
) -> bool:
    if value is None:
        return default
    if context is not None and isinstance(value, str):
        value = context.resolve_value(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        return default if not normalized else normalized in {"true", "yes", "1", "on", "enabled"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def parse_search_region(search_region: dict[str, Any]) -> tuple[int, int, int, int]:
    if not search_region or not isinstance(search_region, dict):
        return (0, 0, 0, 0)
    x = int(search_region.get("x", 0) or 0)
    y = int(search_region.get("y", 0) or 0)
    if "x2" in search_region or "y2" in search_region:
        x2 = int(search_region.get("x2", 0) or 0)
        y2 = int(search_region.get("y2", 0) or 0)
        if x2 < x:
            x, x2 = x2, x
        if y2 < y:
            y, y2 = y2, y
        return x, y, x2 - x, y2 - y
    return (
        x,
        y,
        int(search_region.get("width", 0) or 0),
        int(search_region.get("height", 0) or 0),
    )
