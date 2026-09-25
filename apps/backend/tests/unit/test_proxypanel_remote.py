"""Public catalog shape is observed; non-null schedules and writes are synthetic."""

import json
from pathlib import Path

import httpx
import pytest

from autoflow.domain.proxies.errors import ProviderSchemaError
from autoflow.providers.proxy.proxypanel import ProxyPanelReadProvider
from autoflow.providers.proxy.remote_mapping import locations, schedule, state


def detail():
    body = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/proxypanel/list-redacted.json"
        ).read_text(encoding="utf-8")
    )["proxies"][0]
    return {
        **body,
        "bound": False,
        "rotation_available": False,
        "rotation_blocked_reason": "not_bound",
        "location_generation": 1,
    }


def test_runtime_rotation_condition_does_not_disable_other_controls():
    result = state(detail())
    caps = {c.key: c for c in result.capabilities}
    assert not caps["change_ip"].available and "未绑定" in caps["change_ip"].reason
    assert caps["relocate"].available and caps["rotation_schedule"].available


def test_cooldown_is_machine_readable_without_inventing_remaining_time():
    result = state({**detail(), "rotation_blocked_reason": "cooldown"})
    assert result.rotation_blocked_reason == "cooldown"
    assert result.retry_after_seconds is None
    assert result.rotation_available is False


def test_ready_is_explicit_not_inferred_from_absent_fields():
    ready = state({**detail(), "rotation_available": True, "rotation_blocked_reason": None})
    assert ready.rotation_available is True
    assert ready.rotation_blocked_reason is None


def test_catalog_groups_city_aliases_by_target_without_inventing_capacity():
    rows = [
        {
            "country": "US",
            "city": city,
            "carriers": [
                {
                    "carrier": "T-Mobile",
                    "location_id": "Los_Angeles",
                    "available_slots": 2,
                }
            ],
        }
        for city in ("Arcadia", "Aliso Viejo")
    ]
    result = locations({"locations": rows})
    assert len(result) == 1 and result[0].cities == ("Aliso Viejo", "Arcadia")
    assert result[0].available_slots == 2
    rows[1]["carriers"][0]["available_slots"] = 3
    with pytest.raises(ProviderSchemaError):
        locations({"locations": rows})


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"schedule": {"mode": "random_city", "interval_minutes": 10}},
        {"schedule": {"mode": "same_city", "interval_minutes": True}},
        {"schedule": {"mode": "same_city", "interval_minutes": 61}},
    ],
)
def test_schedule_schema_drift_is_not_reported_as_disabled(value):
    with pytest.raises(ProviderSchemaError):
        schedule(value)


def test_null_and_documented_schedule_modes():
    assert not schedule({"schedule": None}).enabled
    for mode in ("same_city", "same_city_carriers", "full_pool"):
        assert (
            schedule({"schedule": {"mode": mode, "interval_minutes": 10}}).mode == mode
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,method,suffix,payload",
    [
        ("change_ip", "POST", "rotate", {}),
        ("relocate", "POST", "relocate", {"location_id": "Dallas"}),
        (
            "save_rotation",
            "PUT",
            "rotation-schedule",
            {"mode": "full_pool", "interval_minutes": 10},
        ),
        ("clear_rotation", "DELETE", "rotation-schedule", {}),
    ],
)
async def test_commands_use_fixed_origin_and_documented_body_once(
    kind, method, suffix, payload
):
    calls = []

    def respond(request):
        calls.append(request)
        assert (
            str(request.url)
            == f"https://proxypanel.io/api/v1/proxies/test-proxy/{suffix}"
        )
        assert request.method == method
        assert (json.loads(request.content) if request.content else {}) == payload
        return httpx.Response(204)

    await ProxyPanelReadProvider(transport=httpx.MockTransport(respond)).execute(
        b"synthetic-key", "test-proxy", kind, payload
    )
    assert len(calls) == 1
