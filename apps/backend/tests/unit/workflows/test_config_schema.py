"""Remediation M2 R2-11 / AC2-10: executor config schema derived from real reads, with frozen panel debt."""

import ast
import json
from pathlib import Path

from autoflow.application.workflows.config_schema import (
    COMMON_NODE_KEYS,
    production_config_schema,
    read_keys,
    unknown_config_keys,
)
from autoflow.application.workflows.config_schema_debt import PANEL_ONLY_KEYS
from autoflow.application.workflows.config_schema_snapshot import READ_KEYS
from autoflow.bootstrap import executor_schema_export

ROOT = Path(__file__).resolve().parents[5]
INVENTORY = ROOT / "docs/migration/studio-frontend-completion"


def keys(source: str) -> set[str]:
    return read_keys(ast.parse(source))


def test_reads_are_recognised_in_every_supported_shape():
    assert keys('config.get("a"); config["b"]; "c" in config; helper(config, "d")') == {"a", "b", "c", "d"}
    assert keys('for key in ("e", "f"): config.get(key)') == {"e", "f"}
    assert keys('for key, value in (("g", 1), ("h", 2)): config.get(key)') == {"g", "h"}
    assert keys('field = "i" if image else "j"') == {"i", "j"}
    assert keys('print("not a key"); result = {"success": True}; other.get("k")') == set()


def test_the_runtime_snapshot_and_studio_copy_match_the_executor_sources():
    assert executor_schema_export.main(["--check"]) == 0
    assert dict(READ_KEYS) == dict(production_config_schema())


def test_known_executors_report_the_keys_they_read():
    assert {"operation", "name", "value", "domain", "path", "url", "variableName"} <= READ_KEYS["web_cookie"]
    assert {"startX", "startY", "endX", "endY"} <= READ_KEYS["image_ocr"]
    assert {"list1", "list2"} <= READ_KEYS["list_cartesian_product"]
    assert {"temperature", "maxTokens", "modelId"} <= READ_KEYS["ai_chat"]


def test_panel_fields_the_backend_does_not_read_only_shrink():
    capabilities = {item["id"]: item["type"] for item in json.loads((INVENTORY / "capabilities.json").read_text(encoding="utf-8"))}
    cases = json.loads((INVENTORY / "evidence/f2-node-fields/cases.json").read_text(encoding="utf-8"))
    unread: dict[str, set[str]] = {}
    for case in cases:
        field = (case.get("preconditions") or {}).get("field")
        module_type = capabilities.get(case["capability"])
        if ".field." not in case["id"] or not field or module_type not in READ_KEYS:
            continue
        if field not in READ_KEYS[module_type] and field not in COMMON_NODE_KEYS:
            unread.setdefault(module_type, set()).add(field)
    new = {t: sorted(f - PANEL_ONLY_KEYS.get(t, frozenset())) for t, f in unread.items() if f - PANEL_ONLY_KEYS.get(t, frozenset())}
    assert new == {}, "new panel fields need backend reads and behaviour tests (remediation rule 1)"
    stale = {t: sorted(f - unread.get(t, set())) for t, f in PANEL_ONLY_KEYS.items() if f - unread.get(t, set())}
    assert stale == {}, "remove fixed entries from config_schema_debt.PANEL_ONLY_KEYS"


def test_unknown_keys_exclude_reads_shared_fields_and_known_panel_fields():
    data = {"label": "复制", "variableName": "x", "variableValue": "1", "timeout": 3, "selector": "#a", "config": {"waitUntil": "load"}}
    assert unknown_config_keys(data, "set_variable") == ["selector", "waitUntil"]
    assert unknown_config_keys({"apiKey": "k", "userPrompt": "hi"}, "ai_chat") == []
    assert unknown_config_keys({"color": "red", "whatever": 1}, "group") == []
    assert unknown_config_keys({"anything": 1}, "project_data") == []
