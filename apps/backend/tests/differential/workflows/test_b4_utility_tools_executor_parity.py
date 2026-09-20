from __future__ import annotations

import asyncio
import copy
import importlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from threading import Event
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_worker import _ThreadCancellation

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
FROZEN_BACKEND = REPOSITORY_ROOT / "reference" / "WebRPA" / "backend"
FROZEN_HARNESS = Path(__file__).with_name("frozen_utility_tools_harness.py")

CLASS_NAMES = (
    "RandomPasswordGeneratorExecutor",
    "URLEncodeDecodeExecutor",
    "MD5EncryptExecutor",
    "SHAEncryptExecutor",
    "TimestampConverterExecutor",
    "RGBToHSVExecutor",
    "RGBToCMYKExecutor",
    "HEXToCMYKExecutor",
    "UUIDGeneratorExecutor",
)
EXPECTED_TYPES = {
    "random_password_generator",
    "url_encode_decode",
    "md5_encrypt",
    "sha_encrypt",
    "timestamp_converter",
    "rgb_to_hsv",
    "rgb_to_cmyk",
    "hex_to_cmyk",
    "uuid_generator",
}


def _target_module() -> Any:
    try:
        return importlib.import_module(
            "autoflow.application.workflows.executors.utility_tools"
        )
    except ImportError as error:
        pytest.fail(f"utility tools production executor is missing: {error}")


def _target_executors() -> dict[str, type[Any]]:
    module = _target_module()
    try:
        return {
            executor().module_type: executor
            for executor in (getattr(module, name) for name in CLASS_NAMES)
        }
    except AttributeError as error:
        pytest.fail(f"utility tools production executor is missing: {error}")


def _source_result(payload: dict[str, Any]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FROZEN_BACKEND)
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(FROZEN_HARNESS)],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True, encoding="utf-8",
        env=env,
    )
    return json.loads(completed.stdout.splitlines()[-1])


async def _target_result(payload: dict[str, Any]) -> dict[str, Any]:
    module = _target_module()
    generator = random.Random(int(payload.get("seed", 8675309)))
    context = ExecutionContext(variables=copy.deepcopy(payload.get("variables", {})))
    with (
        patch.object(module.secrets, "choice", generator.choice),
        patch.object(
            module.uuid,
            "uuid1",
            lambda: UUID("12345678-1234-1234-9234-123456789abc"),
        ),
        patch.object(
            module.uuid,
            "uuid4",
            lambda: UUID("12345678-1234-4234-9234-123456789abc"),
        ),
    ):
        result = await _target_executors()[payload["type"]]().execute(
            copy.deepcopy(payload["config"]), context
        )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "error": result.error,
        "variables": context.variables,
    }


CASES: list[dict[str, Any]] = [
    {
        "type": "random_password_generator",
        "seed": 17,
        "config": {
            "length": 20,
            "includeUppercase": True,
            "includeLowercase": True,
            "includeDigits": True,
            "includeSymbols": True,
            "resultVariable": "out",
        },
    },
    {
        "type": "random_password_generator",
        "seed": 19,
        "variables": {"length": 8, "enabled": "true"},
        "config": {
            "length": "{length}",
            "includeUppercase": "{enabled}",
            "includeLowercase": False,
            "includeDigits": False,
            "includeSymbols": False,
            "excludeAmbiguous": True,
            "resultVariable": "out",
        },
    },
    {
        "type": "random_password_generator",
        "config": {
            "includeUppercase": False,
            "includeLowercase": False,
            "includeDigits": False,
            "includeSymbols": False,
        },
    },
    {
        "type": "url_encode_decode",
        "config": {
            "inputText": "中文 a/b?x=1",
            "operation": "encode",
            "resultVariable": "out",
        },
    },
    {
        "type": "url_encode_decode",
        "variables": {"encoded": "%E4%B8%AD%E6%96%87%20a"},
        "config": {
            "inputText": "{encoded}",
            "operation": "decode",
            "resultVariable": "out",
        },
    },
    {"type": "url_encode_decode", "config": {"inputText": ""}},
    {
        "type": "md5_encrypt",
        "config": {
            "inputText": "AutoFlow中文",
            "outputFormat": "hex",
            "resultVariable": "out",
        },
    },
    {
        "type": "md5_encrypt",
        "config": {
            "inputText": "AutoFlow",
            "outputFormat": "base64",
            "resultVariable": "out",
        },
    },
    {"type": "md5_encrypt", "config": {"inputText": "", "resultVariable": "out"}},
    {
        "type": "sha_encrypt",
        "config": {
            "inputText": "AutoFlow",
            "shaType": "sha512",
            "outputFormat": "hex",
            "resultVariable": "out",
        },
    },
    {
        "type": "sha_encrypt",
        "config": {
            "inputText": "AutoFlow",
            "shaType": "sha256",
            "outputFormat": "base64",
            "resultVariable": "out",
        },
    },
    {
        "type": "sha_encrypt",
        "config": {
            "inputText": "AutoFlow",
            "shaType": "not-real",
            "outputFormat": "hex",
            "resultVariable": "out",
        },
    },
    {
        "type": "timestamp_converter",
        "config": {
            "operation": "to_timestamp",
            "inputValue": "2026-09-16 12:30:45",
            "timestampUnit": "seconds",
            "resultVariable": "out",
        },
    },
    {
        "type": "timestamp_converter",
        "config": {
            "operation": "to_timestamp",
            "inputValue": "2026/09/16",
            "datetimeFormat": "%Y/%m/%d",
            "timestampUnit": "milliseconds",
            "resultVariable": "out",
        },
    },
    {
        "type": "timestamp_converter",
        "config": {
            "operation": "from_timestamp",
            "inputValue": 1789533045,
            "timestampUnit": "seconds",
            "resultVariable": "out",
        },
    },
    {
        "type": "timestamp_converter",
        "config": {
            "operation": "from_timestamp",
            "inputValue": 0,
            "timestampUnit": "seconds",
            "resultVariable": "out",
        },
    },
    {
        "type": "timestamp_converter",
        "config": {
            "operation": "to_timestamp",
            "inputValue": "bad",
            "resultVariable": "out",
        },
    },
    {
        "type": "rgb_to_hsv",
        "config": {"r": 255, "g": 0, "b": 127, "resultVariable": "out"},
    },
    {
        "type": "rgb_to_hsv",
        "variables": {"r": "128"},
        "config": {"r": "{r}", "g": 128, "b": 128, "resultVariable": "out"},
    },
    {
        "type": "rgb_to_cmyk",
        "config": {"r": 255, "g": 0, "b": 127, "resultVariable": "out"},
    },
    {
        "type": "rgb_to_cmyk",
        "config": {"r": 0, "g": 0, "b": 0, "resultVariable": "out"},
    },
    {"type": "hex_to_cmyk", "config": {"hexColor": "#f08", "resultVariable": "out"}},
    {"type": "hex_to_cmyk", "config": {"hexColor": "336699", "resultVariable": "out"}},
    {
        "type": "hex_to_cmyk",
        "config": {"hexColor": "bad-value", "resultVariable": "out"},
    },
    {"type": "hex_to_cmyk", "config": {"hexColor": "", "resultVariable": "out"}},
    {
        "type": "uuid_generator",
        "config": {
            "uuidVersion": 1,
            "uppercase": True,
            "removeHyphens": True,
            "resultVariable": "out",
        },
    },
    {"type": "uuid_generator", "config": {"uuidVersion": 4, "resultVariable": "out"}},
    {
        "type": "uuid_generator",
        "config": {
            "uuidVersion": 3,
            "namespace": "dns",
            "name": "autoflow.cn",
            "resultVariable": "out",
        },
    },
    {
        "type": "uuid_generator",
        "config": {
            "uuidVersion": 5,
            "namespace": "url",
            "name": "https://autoflow.cn",
            "resultVariable": "out",
        },
    },
    {
        "type": "uuid_generator",
        "config": {
            "uuidVersion": 5,
            "namespace": "",
            "name": "",
            "resultVariable": "out",
        },
    },
]


def test_frozen_source_exposes_exact_approved_utility_family() -> None:
    assert set(_source_result({"operation": "types"})["types"]) == EXPECTED_TYPES


@pytest.mark.parametrize("payload", CASES, ids=lambda case: case["type"])
@pytest.mark.asyncio
async def test_migrated_utility_tools_match_frozen_source(
    payload: dict[str, Any],
) -> None:
    assert await _target_result(payload) == _source_result(payload)


@pytest.mark.asyncio
async def test_random_password_generation_has_a_runtime_capacity_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _target_module()
    monkeypatch.setattr(module.secrets, "choice", lambda charset: charset[0])

    result = await module.RandomPasswordGeneratorExecutor().execute(
        {"length": 1_048_577}, ExecutionContext()
    )

    assert result.success is False
    assert result.error == "生成长度超过工作流安全限制"


@pytest.mark.asyncio
async def test_random_password_generation_cooperatively_observes_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _target_module()
    monkeypatch.setattr(module.secrets, "choice", lambda charset: charset[0])
    stop = Event()
    task = asyncio.create_task(
        module.RandomPasswordGeneratorExecutor().execute(
            {"length": 500_000},
            ExecutionContext(cancellation=_ThreadCancellation(stop)),
        )
    )
    await asyncio.sleep(0)
    stop.set()

    with pytest.raises(asyncio.CancelledError):
        await task
