"""Remediation M3 R3-01: field filters/orders are reported as row-by-row claims, never hidden."""

from autoflow.application.project_automations.service import scan_notices


def test_only_field_filters_or_orders_produce_a_notice():
    plan = {"inputs": [
        {"alias": "账号", "filter": {"type": "all", "items": [{"type": "status", "operator": "isNull"}]}, "orderBy": [{"systemField": "recordKey", "direction": "asc"}]},
        {"alias": "订单", "filter": {"type": "not", "item": {"type": "compare", "fieldId": "f", "operator": "isNull"}}, "orderBy": []},
        {"alias": "人员", "filter": {"type": "all", "items": []}, "orderBy": [{"fieldId": "f", "direction": "desc"}]},
    ]}
    notices = scan_notices(plan)
    assert [(notice.path, notice.code) for notice in notices] == [
        (["inputPlan", "inputs", "1"], "CLAIM_SCAN_REQUIRED"), (["inputPlan", "inputs", "2"], "CLAIM_SCAN_REQUIRED"),
    ]
    assert notices[0].message == "「订单」按字段筛选或排序，数据很多时每次领取需要逐行检查，会慢一些"
