"""Read-only verification of durable Android lifecycle operations."""

from datetime import UTC, datetime
from typing import Any

from autoflow.domain.android.ports import AndroidError


async def verify_lifecycle_operation(
    operations: Any,
    devices: Any,
    record: Any,
    *,
    workspace_identity: str,
) -> Any:
    """Verify a lifecycle result without replaying the lifecycle command.

    A missing repository/runtime observation is deliberately inconclusive. The
    caller must keep the durable operation in ``needs_verification`` until a
    concrete, owned runtime state is observed.
    """
    if devices is None or not hasattr(devices, "runtime"):
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "尚未接入运行时核实，操作保持待核实", 503)
    try:
        device = devices.get(record.target_id)
    except (AndroidError, KeyError, LookupError, OSError, TimeoutError) as error:
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "设备记录不存在，操作结果仍无法核实", 503) from error
    if not isinstance(device, dict):
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "设备记录不存在，操作结果仍无法核实", 503)

    runtime_workspace = getattr(devices.runtime, "workspace_id", None)
    if runtime_workspace is not None and device.get("workspaceId") != runtime_workspace:
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "设备归属无法核实，操作保持待核实", 503)
    if runtime_workspace is None and device.get("workspaceId") not in {None, workspace_identity}:
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "设备归属无法核实，操作保持待核实", 503)

    try:
        verifier = getattr(devices.runtime, "verify_deleted", None) if record.action == "delete" else None
        observed = await (verifier(device) if callable(verifier) else devices.runtime.inspect(device))
    except (AndroidError, TimeoutError, OSError) as error:
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "设备状态仍无法核实", 503) from error
    except Exception as error:
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "设备状态仍无法核实", 503) from error
    status = observed.get("androidStatus") if isinstance(observed, dict) else None
    expected = {"start": {"ready"}, "restart": {"ready"}, "stop": {"stopped", "retained"}}.get(record.action)
    if record.action == "delete":
        expected = {"missing"} if (record.payload or {}).get("deleteData") else {"retained", "missing"}
    if expected is None or status not in expected:
        raise AndroidError("ANDROID_VERIFICATION_UNAVAILABLE", "设备状态与操作结果不一致，请继续核实", 503)

    device["androidStatus"] = status
    if record.action == "delete":
        device["deleted"] = status == "missing"
        device["dataRetained"] = status == "retained"
    device["control"] = "idle"
    device["lastError"] = None
    device.setdefault("operation", {}).update(
        id=record.operation_id,
        action=record.action,
        state="succeeded",
        stage="已核实",
        error=None,
        finishedAt=datetime.now(UTC).isoformat(),
    )
    changes = {"stage_code": "verified", "result_code": "STATE_VERIFIED"}
    transition_with_device = getattr(operations, "transition_with_device", None)
    if callable(transition_with_device):
        return transition_with_device(record.operation_id, "needs_verification", "succeeded", changes, device)
    result = operations.transition(record.operation_id, "needs_verification", "succeeded", changes)
    repository = getattr(devices, "repository", None)
    if repository is not None and hasattr(repository, "save"):
        repository.save(device)
    return result
