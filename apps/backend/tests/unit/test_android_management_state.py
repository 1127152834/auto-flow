from autoflow.adapters.http.android_management_schemas import ManagementDeviceRead
from autoflow.domain.android.management_models import DeviceFacts
from autoflow.domain.android.management_rules import display_state, policy_for


def test_active_delete_operation_is_not_presented_as_starting() -> None:
    facts = DeviceFacts(
        device_id="device",
        runtime_state="ready",
        control="managing",
        operation_action="delete",
        operation_state="running",
    )

    assert display_state(facts) == "正在删除"
    assert "start" not in policy_for(facts).allowed_actions


def test_unknown_or_stale_device_only_allows_verification() -> None:
    facts = DeviceFacts(device_id="device", runtime_state="unknown", stale=True)

    policy = policy_for(facts)

    assert policy.allowed_actions == ("verify",)
    assert policy.blocked_reasons["start"]
    assert display_state(facts) == "待核实"


def test_retained_device_requires_restore() -> None:
    facts = DeviceFacts(device_id="device", runtime_state="retained")

    policy = policy_for(facts)

    assert "restore" in policy.allowed_actions
    assert "start" not in policy.allowed_actions
    assert display_state(facts) == "数据已保留"


def test_management_device_schema_uses_camel_case_without_runtime_secrets() -> None:
    result = ManagementDeviceRead(
        device_id="device",
        revision=2,
        name="测试设备",
        runtime_state="ready",
        owner={"kind": "none", "id": None},
        observed_at=None,
        stale=False,
        spec_snapshot={"width": 720, "height": 1280},
        latest_operation=None,
        allowed_actions=["open"],
        blocked_reasons={},
    )

    payload = result.model_dump(by_alias=True)
    assert payload["deviceId"] == "device"
    assert "containerId" not in payload
