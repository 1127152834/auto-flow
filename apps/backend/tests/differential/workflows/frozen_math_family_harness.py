from __future__ import annotations

import asyncio
import io
import json
import math
import random
import sys
from contextlib import redirect_stdout
from typing import Any

from app.executors.base import ExecutionContext
from app.executors.math_advanced import (
    MathClampExecutor,
    MathExpExecutor,
    MathFactorialExecutor,
    MathGcdExecutor,
    MathLcmExecutor,
    MathLogExecutor,
    MathPercentageExecutor,
    MathPermutationExecutor,
    MathRandomAdvancedExecutor,
    MathTrigExecutor,
)
from app.executors.math_list_ops import (
    ListAverageExecutor,
    ListMaxExecutor,
    ListMinExecutor,
    ListSliceExecutor,
    ListSortExecutor,
    ListSumExecutor,
    ListUniqueExecutor,
    MathAbsExecutor,
    MathBaseConvertExecutor,
    MathFloorExecutor,
    MathModuloExecutor,
    MathPowerExecutor,
    MathRoundExecutor,
    MathSqrtExecutor,
)
from app.executors.statistics import (
    MedianExecutor,
    ModeExecutor,
    NormalizeExecutor,
    PercentileExecutor,
    StandardizeExecutor,
    StdevExecutor,
    VarianceExecutor,
)

SOURCE_EXECUTORS = {
    executor().module_type: executor
    for executor in (
        ListSumExecutor,
        ListAverageExecutor,
        ListMaxExecutor,
        ListMinExecutor,
        ListSortExecutor,
        ListUniqueExecutor,
        ListSliceExecutor,
        MathRoundExecutor,
        MathBaseConvertExecutor,
        MathFloorExecutor,
        MathModuloExecutor,
        MathAbsExecutor,
        MathSqrtExecutor,
        MathPowerExecutor,
        MathLogExecutor,
        MathTrigExecutor,
        MathExpExecutor,
        MathGcdExecutor,
        MathLcmExecutor,
        MathFactorialExecutor,
        MathPermutationExecutor,
        MathPercentageExecutor,
        MathClampExecutor,
        MathRandomAdvancedExecutor,
        MedianExecutor,
        ModeExecutor,
        VarianceExecutor,
        StdevExecutor,
        PercentileExecutor,
        NormalizeExecutor,
        StandardizeExecutor,
    )
}


def normalize(value: Any) -> Any:
    if isinstance(value, complex):
        return {
            "__type__": "complex",
            "real": normalize(value.real),
            "imag": normalize(value.imag),
        }
    if isinstance(value, float) and not math.isfinite(value):
        return {
            "__type__": "float",
            "value": "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf"),
        }
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return value


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("operation") == "types":
        return {"types": sorted(SOURCE_EXECUTORS)}
    random.seed(payload.get("seed", 8675309))
    context = ExecutionContext(variables=payload.get("variables", {}))
    result = await SOURCE_EXECUTORS[payload["type"]]().execute(
        payload["config"], context
    )
    return normalize(
        {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
            "branch": result.branch,
            "variables": context.variables,
        }
    )


if __name__ == "__main__":
    output = io.StringIO()
    payload = json.load(sys.stdin)
    with redirect_stdout(output):
        result = asyncio.run(run(payload))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
