"""Saved browser identity uses a complete snapshot, never a live template."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, fields
from datetime import datetime
from typing import Any

from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.runtime import WorkflowRuntimeError, thaw_json


def profile_from_request(request: Mapping[str, Any]) -> Profile:
    snapshot = thaw_json(request.get("frozenConfiguration"))
    try:
        profile_id = request["profileId"]
        if not isinstance(profile_id, str) or not profile_id:
            raise ValueError
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "profileSpec", "fingerprintSeed", "createdAt", "updatedAt",
        }:
            raise ValueError
        values = snapshot["profileSpec"]
        if not isinstance(values, dict) or set(values) != {item.name for item in fields(ProfileSpec)}:
            raise ValueError
        if type(snapshot["fingerprintSeed"]) is not int:
            raise ValueError
        profile = Profile(
            profile_id, ProfileSpec.from_values(deepcopy(values)), snapshot["fingerprintSeed"],
            datetime.fromisoformat(snapshot["createdAt"]), datetime.fromisoformat(snapshot["updatedAt"]),
        )
        if request.get("kernelId") != f"{profile.spec.browser_edition}:{profile.spec.browser_version}":
            raise ValueError
        return profile
    except (KeyError, TypeError, ValueError):
        raise WorkflowRuntimeError("WORKFLOW_RESOURCE_INVALID", "浏览器资源快照无效", 422) from None


def identity_from_request(request: Mapping[str, Any]) -> dict[str, Any]:
    profile = profile_from_request(request)
    return {
        "schemaVersion": 1,
        "profileId": profile.id,
        "kernelId": f"{profile.spec.browser_edition}:{profile.spec.browser_version}",
        "frozenConfiguration": {
            "profileSpec": asdict(profile.spec), "fingerprintSeed": profile.fingerprint_seed,
            "createdAt": profile.created_at.isoformat(), "updatedAt": profile.updated_at.isoformat(),
        },
    }


def request_from_identity(identity: Any) -> dict[str, Any]:
    identity = thaw_json(identity)
    if not isinstance(identity, dict) or type(identity.get("schemaVersion")) is not int or identity["schemaVersion"] != 1:
        raise WorkflowRuntimeError(
            "ENVIRONMENT_IDENTITY_UNVERIFIED", "原身份资料缺失或版本不支持，无法恢复环境", 409,
        )
    if set(identity) != {"schemaVersion", "profileId", "kernelId", "frozenConfiguration"}:
        raise WorkflowRuntimeError("WORKFLOW_RESOURCE_INVALID", "环境身份资料无效", 422)
    normalized = identity_from_request(identity)
    return {"browser": "persistent", **{key: value for key, value in normalized.items() if key != "schemaVersion"}}
