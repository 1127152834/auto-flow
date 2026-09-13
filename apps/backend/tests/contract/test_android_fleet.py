import asyncio
from copy import deepcopy
from time import monotonic, sleep
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.fixtures.workflow_control import node, payload
from tests.fixtures.workflow_runs import workflow_runtime
from tests.unit.test_android_handoff import Runtime

BASE = "/api/v1/android"


class Stream:
    width, height, error = 720, 1280, None

    def __init__(self, runtime):
        self.commands = []

    async def start(self):
        pass

    async def command(self, command):
        self.commands.append(deepcopy(command))

    async def close(self):
        pass


class Pool(Runtime):
    def for_device(self, identifier):
        value = Runtime()
        value.connect = AsyncMock()
        value.inspect = AsyncMock(return_value={"androidStatus": "ready"})
        return value


def setup(tmp_path):
    app, _, _ = workflow_runtime(tmp_path)
    service = app.state.android_service
    service.runtime = Pool()
    service.runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    app.state.android_console.stream_factory = Stream
    ids = [str(uuid4()), str(uuid4())]
    for identifier in ids:
        service.repository.save(
            {
                "deviceId": identifier,
                "name": "device",
                "runtimeId": "test",
                "control": "idle",
                "ownerRunId": None,
                "generation": 0,
                "width": 720,
                "height": 1280,
                "imageId": "sha256:" + "a" * 64,
            }
        )
    return app, ids


def test_sessions_are_per_device_reject_duplicate_input_and_share_native_lease(
    tmp_path,
):
    app, ids = setup(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        request = {"deviceId": ids[0], "access": "manual", "requestId": str(uuid4())}
        first = client.post(BASE + "/sessions", json=request)
        assert first.status_code == 200, first.text
        a = first.json()
        assert client.post(BASE + "/sessions", json=request).json() == a
        b = client.post(
            BASE + "/sessions",
            json={**request, "deviceId": ids[1], "requestId": str(uuid4())},
        )
        assert b.status_code == 200, b.text
        assert (
            client.post(
                BASE + "/sessions", json={**request, "requestId": str(uuid4())}
            ).status_code
            == 409
        )
        input_path = f"{BASE}/sessions/{a['id']}/input"
        body = {
            "generation": a["generation"],
            "sequence": 1,
            "kind": "text",
            "text": "中文测试",
        }
        assert client.post(input_path, json=body).status_code == 200
        assert client.post(input_path, json=body).status_code == 409
        action = {
            "generation": a["generation"],
            "requestId": str(uuid4()),
            "action": "native",
        }
        native = client.post(f"{BASE}/sessions/{a['id']}/actions", json=action)
        assert native.status_code == 200, native.text
        assert client.post(input_path, json={**body, "sequence": 2}).status_code == 409
        assert (
            client.post(f"{BASE}/sessions/{a['id']}/actions", json=action).status_code
            == 200
        )
        assert len(app.state.android_console.sessions) == 2


def test_batches_project_private_snapshot_and_are_idempotent(tmp_path):
    app, _ = setup(tmp_path)
    profile = {
        "id": str(uuid4()),
        "revision": 1,
        "name": "Android 13",
        "imageId": "sha256:" + "a" * 64,
        "width": 720,
        "height": 1280,
        "dpi": 320,
        "cpu": 1,
        "memoryMb": 1536,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "shellRoot": "unknown",
        "applicationRoot": "unknown",
    }
    app.state.android_fleet.resources.save("profile", profile)
    app.state.android_fleet.tick = AsyncMock()
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        body = {
            "batchId": str(uuid4()),
            "name": "Batch",
            "profileId": profile["id"],
            "profileRevision": 1,
        }
        response = client.post(BASE + "/batches", json=body)
        assert response.status_code == 202, response.text
        assert len(response.json()["items"]) == 3
        assert "profile" not in response.json()
        assert client.post(BASE + "/batches", json=body).json() == response.json()
        assert (
            client.post(BASE + "/batches", json={**body, "quantity": 2}).status_code
            == 409
        )
        assert client.get(BASE + "/batches").status_code == 200
        assert len({item["deviceId"] for item in response.json()["items"]}) == 3


def test_takeover_waits_for_action_boundary_and_continues_without_replaying(tmp_path):
    app, ids = setup(tmp_path)
    runtime = app.state.android_service.runtime
    gate, entered = asyncio.Event(), asyncio.Event()
    calls = []
    original = runtime.for_device

    def factory(identifier):
        ctx = original(identifier)

        async def command(operation, args, timeout):
            calls.append(args["key"])
            if len(calls) == 1:
                entered.set()
                await gate.wait()
            return b""

        ctx.command = command
        return ctx

    runtime.for_device = factory
    graph = payload(
        [
            node("one", "android_key", key="HOME"),
            node("two", "android_key", key="BACK"),
        ],
        [("one", "out", "two")],
    )
    rid = str(uuid4())
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        response = client.post(
            "/api/v1/workflows/runs",
            json={
                "runId": rid,
                "target": {"kind": "android", "deviceId": ids[0]},
                **graph,
            },
        )
        assert response.status_code == 201, response.text
        client.portal.call(entered.wait)
        session = client.post(
            BASE + "/sessions",
            json={"requestId": str(uuid4()), "deviceId": ids[0], "access": "readonly"},
        ).json()
        path = f"{BASE}/sessions/{session['id']}"

        def act(action):
            return client.post(
                path + "/actions",
                json={
                    "generation": session["generation"],
                    "requestId": str(uuid4()),
                    "action": action,
                },
            )

        assert act("takeover").status_code == 200
        assert act("embedded").status_code == 409
        assert calls == ["HOME"]
        client.portal.call(gate.set)
        deadline = monotonic() + 5
        while monotonic() < deadline:
            run = client.get("/api/v1/workflows/runs/" + rid).json()
            if run["state"] == "waiting_manual":
                break
            sleep(0.02)
        assert run["state"] == "waiting_manual", run
        granted = act("embedded")
        assert granted.status_code == 200, granted.text
        session = granted.json()
        assert (
            client.post(
                path + "/input",
                json={
                    "generation": session["generation"],
                    "sequence": 1,
                    "kind": "text",
                    "text": "中文",
                },
            ).status_code
            == 200
        )
        assert calls == ["HOME"]
        assert act("resume").status_code == 200
        deadline = monotonic() + 5
        while monotonic() < deadline:
            run = client.get("/api/v1/workflows/runs/" + rid).json()
            if run["state"] == "succeeded":
                break
            sleep(0.02)
        assert run["state"] == "succeeded", run
        assert calls == ["HOME", "BACK"]


def test_cleanup_failure_can_be_retried_without_reopening_input(tmp_path):
    from autoflow.domain.android.ports import AndroidError

    app, ids = setup(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        view = client.post(
            BASE + "/sessions",
            json={"requestId": str(uuid4()), "deviceId": ids[0], "access": "manual"},
        ).json()
        session = app.state.android_console.sessions[view["id"]]
        cleanup = session["context"].cleanup
        session["context"].cleanup = AsyncMock(
            side_effect=AndroidError("ANDROID_CLEANUP_FAILED", "unconfirmed")
        )
        path = BASE + "/sessions/" + view["id"]
        request = {
            "requestId": str(uuid4()),
            "generation": view["generation"],
            "action": "end",
        }
        assert client.post(path + "/actions", json=request).status_code == 409
        assert client.get(path).json()["state"] == "recovery_required"
        assert (
            client.post(
                path + "/input",
                json={
                    "generation": view["generation"],
                    "sequence": 1,
                    "kind": "text",
                    "text": "blocked",
                },
            ).status_code
            == 409
        )
        session["context"].cleanup = cleanup
        assert client.post(path + "/actions", json=request).json()["state"] == "closed"


def test_idle_readonly_session_can_gain_control_with_a_new_generation(tmp_path):
    app, ids = setup(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        view = client.post(
            BASE + "/sessions",
            json={"requestId": str(uuid4()), "deviceId": ids[0], "access": "readonly"},
        ).json()
        path = BASE + "/sessions/" + view["id"]
        upgraded = client.post(
            path + "/actions",
            json={
                "requestId": str(uuid4()),
                "generation": view["generation"],
                "action": "embedded",
            },
        )
        assert upgraded.status_code == 200, upgraded.text
        assert upgraded.json()["access"] == "manual"
        assert upgraded.json()["generation"] == view["generation"] + 1
        command = {
            "generation": view["generation"],
            "sequence": 1,
            "kind": "text",
            "text": "stale",
        }
        assert client.post(path + "/input", json=command).status_code == 409
        command["generation"] = upgraded.json()["generation"]
        assert client.post(path + "/input", json=command).status_code == 200


def test_multipart_apk_install_respects_manual_lease(tmp_path):
    app, ids = setup(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        view = client.post(
            BASE + "/sessions",
            json={"requestId": str(uuid4()), "deviceId": ids[0], "access": "manual"},
        ).json()
        runtime = app.state.android_console.sessions[view["id"]]["context"].runtime
        runtime.install_apk = AsyncMock()
        path = (
            BASE
            + "/sessions/"
            + view["id"]
            + "/apps/install?generation="
            + str(view["generation"])
        )
        result = client.post(
            path,
            files={
                "file": (
                    "sample.apk",
                    b"PKtest-only",
                    "application/vnd.android.package-archive",
                )
            },
        )
        assert result.status_code == 200, result.text
        runtime.install_apk.assert_awaited_once_with(b"PKtest-only")
        assert (
            client.post(path, files={"file": ("bad.apk", b"invalid")}).status_code
            == 422
        )
