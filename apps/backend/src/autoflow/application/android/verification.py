"""Read-only verification of durable Android lifecycle operations."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from autoflow.domain.android.management_rules import restore_pending
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

    expected_device = deepcopy(device)
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

    lock = getattr(devices.runtime, "lock", None)
    if callable(lock):
        lock()
    try:
        current = devices.get(record.target_id)
        if (
            current != expected_device
            or current.get("ownerRunId")
            or current.get("control") not in {"idle", "recovery_required"}
            or current.get("pendingCommand")
            or (restore_pending(current) and not (record.action == "delete" and (record.payload or {}).get("deleteData")))
            or (current.get("operation") or {}).get("id") != record.operation_id
        ):
            raise AndroidError("ANDROID_OPERATION_STATE_CONFLICT", "设备或控制归属已变化，不能应用历史操作状态", 409)
        device = deepcopy(expected_device)
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
            return transition_with_device(record.operation_id, "needs_verification", "succeeded", changes, device, expected_device=expected_device)
        result = operations.transition(record.operation_id, "needs_verification", "succeeded", changes)
        repository = getattr(devices, "repository", None)
        if repository is not None and hasattr(repository, "save"):
            repository.save(device)
        return result
    finally:
        if callable(lock):
            devices.runtime.unlock()
