"""End-to-end local HTTP/SQLite lifecycle with a synthetic provider; no live writes."""

import asyncio
import time
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from autoflow.bootstrap import proxies as composition
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.proxies.errors import ProviderUnavailableError
from autoflow.domain.proxies.models import Capability, ProviderPage, ProviderProxy
from autoflow.domain.proxies.remote import Location, RemoteState, RotationSchedule
from autoflow.providers.proxy.proxypanel import ProxyPanelHttpError


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def read(self, key):
        return self.values.get(key)

    def write(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class RemoteFixture:
    def __init__(self):
        self.proxy = ProviderProxy(
            "synthetic-1",
            "Synthetic",
            remote_status="active",
            city="Dallas",
            carrier="T-Mobile",
        )
        self.state = RemoteState(
            self.proxy,
            "192.0.2.1",
            0,
            True,
            "US",
            tuple(
                Capability(k, True, "confirmed-authenticated-doc")
                for k in ("change_ip", "relocate", "rotation_schedule")
            ),
        )
        self.schedule = RotationSchedule()
        self.calls = []
        self.behavior = "success"
        self.delay = 0
        self.slots = 2

    async def verify(self, key):
        return ProviderPage((), "unknown")

    async def list_proxies(self, key):
        return ProviderPage((self.proxy,), "complete", 1)

    async def get_state(self, key, provider_id):
        if self.calls and self.behavior == "read_rejected":
            raise ProxyPanelHttpError("PROXYPANEL_AUTH_FAILED", "已发送后的读取失败")
        return self.state

    async def get_locations(self, key):
        return [
            Location(
                "target",
                "Arcadia / Aliso Viejo",
                "US",
                "T-Mobile",
                self.slots,
                ("Arcadia", "Aliso Viejo"),
            )
        ]

    async def get_schedule(self, key, provider_id):
        return self.schedule

    async def execute(self, key, provider_id, kind, payload):
        self.calls.append((kind, payload))
        await asyncio.sleep(self.delay)
        if self.behavior == "timeout":
            raise ProviderUnavailableError("synthetic network interruption")
        if self.behavior == "reject":
            raise ProxyPanelHttpError(
                "PROXYPANEL_RATE_LIMITED", "请求受限", retry_after=12
            )
        if self.behavior in ("unchanged", "read_rejected"):
            return
        if kind == "change_ip":
            self.state = replace(self.state, current_ip="192.0.2.2")
        elif kind == "relocate":
            self.state = replace(
                self.state,
                location_generation=1,
                proxy=replace(self.proxy, city="Arcadia"),
            )
        elif kind == "save_rotation":
            self.schedule = RotationSchedule(
                True, payload["mode"], payload["interval_minutes"]
            )
        else:
            self.schedule = RotationSchedule()


@pytest.fixture
def remote(tmp_path, monkeypatch):
    provider = RemoteFixture()
    monkeypatch.setattr(composition, "LazySystemCredentialStore", MemoryCredentials)
    monkeypatch.setattr(composition, "ProxyPanelReadProvider", lambda: provider)
    app = create_app(
        Settings(data_dir=str(tmp_path), instance_id="test", instance_token="token")
    )
    with TestClient(app, headers={"x-autoflow-token": "token"}) as client:
        app.state.proxy_remote_controls._budget = 0.12
        app.state.proxy_remote_controls._poll = 0.01
        connection = client.post(
            "/api/v1/proxy-panel/connections",
            json={"name": "Test", "api_key": "synthetic-secret"},
        ).json()
        client.post(f"/api/v1/proxy-panel/connections/{connection['id']}/sync", json={})
        proxy = client.get("/api/v1/proxies").json()["items"][0]
        yield client, provider, proxy, app.state.proxy_remote_controls


def submit(remote, route="change-ip", method="POST", extra=None, key=None):
    client, _, proxy, _ = remote
    return client.request(
        method,
        f"/api/v1/proxies/{proxy['id']}/{route}",
        json={"expected_revision": proxy["revision"], **(extra or {})},
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def wait(client, operation_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/proxy-operations/{operation_id}")
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] not in ("queued", "running"):
            return result
        time.sleep(0.01)
    pytest.fail("operation never settled")


def test_confirmed_rotation_updates_projection_preserving_local_metadata(remote):
    client, provider, proxy, _ = remote
    patched = client.patch(
        f"/api/v1/proxies/{proxy['id']}",
        json={
            "expected_revision": proxy["revision"],
            "name_override": "Local alias",
            "enabled": False,
        },
    ).json()
    proxy.update(patched)
    accepted = submit(remote)
    assert accepted.status_code == 202
    result = wait(client, accepted.json()["operation_id"])
    assert result["status"] == "succeeded"
    current = client.get(f"/api/v1/proxies/{proxy['id']}").json()
    assert (
        current["exit_ip"] == "192.0.2.2"
        and current["name_override"] == "Local alias"
        and not current["enabled"]
    )
    assert current["health"]["state"] == "untested"
    assert len(provider.calls) == 1
    assert (
        "secret_ref" not in result
        and "before" not in result
        and "payload" not in result
    )
    assert (
        client.get(f"/api/v1/proxies/{proxy['id']}/operation").json()["id"]
        == result["id"]
    )


def test_idempotency_replay_and_per_proxy_serialization(remote):
    client, provider, _, _ = remote
    provider.delay = 0.06
    key = str(uuid4())
    first = submit(remote, key=key).json()
    assert submit(remote, key=key).json()["operation_id"] == first["operation_id"]
    assert submit(remote).status_code == 409
    assert (
        submit(
            remote, route="relocate", extra={"location_id": "target"}, key=key
        ).status_code
        == 409
    )
    assert wait(client, first["operation_id"])["status"] == "succeeded"
    assert submit(remote, key=key).json()["operation_id"] == first["operation_id"]
    assert len(provider.calls) == 1


@pytest.mark.parametrize("behavior", ["timeout", "unchanged", "read_rejected"])
def test_uncertain_result_blocks_new_write_and_reconcile_never_resends(
    remote, behavior
):
    client, provider, _, _ = remote
    provider.behavior = behavior
    result = wait(client, submit(remote).json()["operation_id"])
    assert result["status"] == "unknown"
    assert submit(remote).status_code == 409
    provider.behavior = "success"
    provider.state = replace(provider.state, current_ip="192.0.2.3")
    response = client.post(f"/api/v1/proxy-operations/{result['id']}/reconcile")
    assert response.json()["status"] == "running"
    assert wait(client, result["id"])["status"] == "succeeded"
    assert len(provider.calls) == 1


def test_actual_not_bound_reason_blocks_only_rotation(remote):
    client, provider, _, _ = remote
    provider.state = replace(
        provider.state,
        bound=False,
        capabilities=(
            Capability("change_ip", False, "confirmed-authenticated-doc", "未绑定"),
            *provider.state.capabilities[1:],
        ),
    )
    result = wait(client, submit(remote).json()["operation_id"])
    assert result["status"] == "failed" and "未绑定" in result["error"]["message"]
    assert not provider.calls
    assert (
        wait(
            client,
            submit(remote, "relocate", extra={"location_id": "target"}).json()[
                "operation_id"
            ],
        )["status"]
        == "succeeded"
    )


def test_location_capacity_revalidated_before_write(remote):
    client, provider, _, _ = remote
    provider.slots = 0
    result = wait(
        client,
        submit(remote, "relocate", extra={"location_id": "target"}).json()[
            "operation_id"
        ],
    )
    assert result["status"] == "failed" and not provider.calls


def test_explicit_rejection_keeps_retry_after(remote):
    client, provider, _, _ = remote
    provider.behavior = "reject"
    result = wait(client, submit(remote).json()["operation_id"])
    assert result["status"] == "failed" and result["error"]["retry_after_seconds"] == 12
    assert len(provider.calls) == 1


def test_schedule_save_readback_clear_and_validation(remote):
    client, provider, proxy, _ = remote
    assert (
        submit(
            remote,
            "rotation-schedule",
            "PUT",
            {"mode": "random_city", "interval_minutes": 10},
        ).status_code
        == 422
    )
    assert (
        submit(
            remote,
            "rotation-schedule",
            "PUT",
            {"mode": "same_city", "interval_minutes": 600},
        ).status_code
        == 422
    )
    result = wait(
        client,
        submit(
            remote,
            "rotation-schedule",
            "PUT",
            {"mode": "full_pool", "interval_minutes": 10},
        ).json()["operation_id"],
    )
    assert result["status"] == "succeeded"
    assert (
        client.get(f"/api/v1/proxies/{proxy['id']}/rotation-schedule").json()["mode"]
        == "full_pool"
    )
    assert (
        wait(
            client, submit(remote, "rotation-schedule", "DELETE").json()["operation_id"]
        )["status"]
        == "succeeded"
    )
    assert len(provider.calls) == 2


def test_restart_recovery_does_not_replay_records(remote):
    client, provider, _, service = remote
    provider.behavior = "unchanged"
    result = wait(client, submit(remote).json()["operation_id"])
    service.operations.update(result["id"], "running")
    service.operations.recover()
    assert service.operations.get(result["id"]).status == "unknown"
    assert len(provider.calls) == 1
    assert (
        client.post(f"/api/v1/proxy-operations/{result['id']}/acknowledge").json()[
            "status"
        ]
        == "failed"
    )
    assert len(provider.calls) == 1


def test_key_replacement_during_write_cannot_apply_old_observation(remote):
    client, provider, proxy, _ = remote
    provider.delay = 0.1
    accepted = submit(remote).json()
    deadline = time.monotonic() + 1
    while not provider.calls and time.monotonic() < deadline:
        time.sleep(0.005)
    connection = client.get("/api/v1/proxy-panel/connections").json()["items"][0]
    response = client.put(
        f"/api/v1/proxy-panel/connections/{connection['id']}/api-key",
        json={
            "expected_revision": connection["revision"],
            "api_key": "replacement-synthetic-key",
        },
    )
    assert response.status_code == 200
    result = wait(client, accepted["operation_id"])
    assert result["status"] == "unknown"
    current = client.get(f"/api/v1/proxies/{proxy['id']}").json()
    assert current["exit_ip"] != "192.0.2.2"
    assert len(provider.calls) == 1


def test_shutdown_marks_sent_operation_unknown_and_recovery_never_resends(remote):
    client, provider, _, service = remote
    provider.delay = 10
    accepted = submit(remote).json()
    deadline = time.monotonic() + 1
    while not provider.calls and time.monotonic() < deadline:
        time.sleep(0.005)
    client.portal.call(service.close)
    assert service.operations.get(accepted["operation_id"]).status == "unknown"
    service.operations.recover()
    assert len(provider.calls) == 1


def test_database_serializes_concurrent_reservations(remote):
    from concurrent.futures import ThreadPoolExecutor

    from autoflow.domain.proxies.errors import OperationInProgressError

    client, provider, proxy, service = remote
    provider.behavior = "unchanged"
    result = wait(client, submit(remote).json()["operation_id"])
    original = service.operations.get(result["id"])
    service.acknowledge(original.id)

    def reserve(_):
        value = replace(
            original, id=str(uuid4()), idempotency_key=str(uuid4()), status="queued"
        )
        try:
            return service.operations.reserve(value, proxy["revision"]).id
        except OperationInProgressError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, range(2)))
    assert sum(value is not None for value in results) == 1
    service.operations.recover()
    assert (
        service.operations.get(next(value for value in results if value)).status
        == "failed"
    )
    assert len(provider.calls) == 1
