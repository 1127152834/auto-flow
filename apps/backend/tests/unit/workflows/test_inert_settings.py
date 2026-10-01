"""Remediation M1 R1-02: backend and Studio agree on which saved settings are inert."""

import re
from pathlib import Path

from autoflow.domain.workflows.inert_settings import INERT_SETTING_KEYS, describe_inert_keys, inert_keys

FRONTEND = Path(__file__).parents[5] / "apps/desktop/src/renderer/domains/workflows/lib/inertSettings.ts"


def test_rules_report_only_settings_that_would_have_changed_behaviour():
    assert inert_keys({"retryCount": 2, "retryDelay": 1, "timeoutAction": "retry"}, "click_element") == [
        "retryCount", "retryDelay", "timeoutAction",
    ]
    assert inert_keys({"retryCount": 0, "retryDelay": 5, "timeoutAction": "stop", "errorPolicy": {"mode": "stop"}}, "click_element") == []
    assert inert_keys({"config": {"onTimeout": "skip", "errorPolicy": {"mode": "continue"}}}, "loop") == ["errorPolicy", "onTimeout"]
    assert inert_keys({"onTimeout": "skip"}, "open_page") == []
    assert inert_keys({"retryCount": "{n}"}, "click_element") == []


def test_description_names_the_node_and_settings():
    assert describe_inert_keys("点击提交", ["retryCount", "timeoutAction"]) == "「点击提交」的以下设置尚未生效，运行时会被忽略：重试次数、运行超时后"


def test_frontend_mirror_lists_the_same_keys():
    declared = re.search(r"INERT_SETTING_KEYS = \[(.*?)\] as const", FRONTEND.read_text(encoding="utf-8")).group(1)
    assert tuple(re.findall(r"'(\w+)'", declared)) == INERT_SETTING_KEYS
