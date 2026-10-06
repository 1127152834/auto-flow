import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autoflow.application.android import ai_tests
from autoflow.application.android.ai_tests import AiTestService
from autoflow.application.models.service import ModelExecutionBinding
from autoflow.domain.android.ports import AndroidError
from autoflow.domain.models.errors import ModelError
from autoflow.domain.models.models import ProviderConnection
from autoflow.infrastructure.database.android_ai_tests import AiTestRepository
from autoflow.infrastructure.database.models import Base
from autoflow.providers.android.artemis_tool import ARTEMIS_COMMIT, ToolStatus

SECRET = "sk-very-secret-777"


class RecordingRepository(AiTestRepository):
    """Real repository that remembers every value written, for the secret scan."""

    def __init__(self, sessions: Any) -> None:
        super().__init__(sessions)
        self.writes: list[str] = []

    def create(self, run: dict[str, Any]) -> dict[str, Any]:
        self.writes.append(json.dumps(run, ensure_ascii=False))
        return super().create(run)

    def update(self, run_id: str, **changes: Any) -> dict[str, Any]:
        self.writes.append(json.dumps(changes, ensure_ascii=False))
        return super().update(run_id, **changes)

    def append_step(self, run_id: str, step: dict[str, Any]) -> None:
        self.writes.append(json.dumps(step, ensure_ascii=False))
        super().append_step(run_id, step)


class FakeTool:
    def __init__(self) -> None:
        self.state = "ready"
        self.helper_installed = True
        self.helper_calls: list[tuple[str, bool]] = []
        self.runs: list[dict[str, Any]] = []
        self.behaviour = "succeed"
        self.gate = asyncio.Event()
        self.gate.set()
        self.install_gate = asyncio.Event()
        self.installs = 0

    def status(self) -> ToolStatus:
        return ToolStatus(self.state, ARTEMIS_COMMIT if self.state == "ready" else None)

    async def install(self, on_output: Any) -> ToolStatus:
        self.installs += 1
        self.state = "installing"
        on_output("下载中")
        await self.install_gate.wait()
        self.state = "ready"
        return self.status()

    async def helper(self, serial: str, *, install: bool) -> bool:
        self.helper_calls.append((serial, install))
        if install:
            self.helper_installed = True
            return True
        return self.helper_installed

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        self.runs.append(kwargs)
        await kwargs["on_event"]({"type": "step", "index": 1, "summary": "打开设置", "screenshot": "step-001.jpg"})
        if self.behaviour == "timeout":
            raise AndroidError("AI_TEST_TIMEOUT", "测试超过 30 秒未完成，已结束", 504)
        if self.behaviour == "crash":
            raise RuntimeError(f"boom with {kwargs['model'].secret}")
        if self.behaviour == "wait":
            cancel_wait = asyncio.create_task(kwargs["cancel"].wait())
            gate_wait = asyncio.create_task(self.gate.wait())
            done, pending = await asyncio.wait({cancel_wait, gate_wait}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            if cancel_wait in done:
                raise AndroidError("AI_TEST_CANCELLED", "测试已停止", 409)
        return {"type": "result", "succeeded": True, "error": None, "traceId": "t-1", "artifacts": ["step-001.jpg"]}


class FakeRuntime:
    def __init__(self) -> None:
        self.serial: str | None = None


class FakeContext:
    def __init__(self, devices: "FakeDevices", device_id: str) -> None:
        self.devices, self.device_id = devices, device_id
        self.runtime = FakeRuntime()
        self.claims: list[tuple[str, str, str]] = []
        self.cleanups = 0

    def claim(self, device_id: str, run_id: str, control: str = "workflow") -> dict[str, Any]:
        device = self.devices.store[device_id]
        if device["control"] != "idle":
            raise AndroidError("ANDROID_BUSY", "设备已占用或需要恢复")
        device.update(control=control, ownerRunId=run_id)
        self.claims.append((device_id, run_id, control))
        return device

    async def connect(self) -> None:
        if self.devices.connect_error:
            raise AndroidError("ANDROID_CONNECT_FAILED", "连接失败", 502)
        self.runtime.serial = "127.0.0.1:41234"

    async def cleanup(self) -> None:
        self.cleanups += 1
        self.runtime.serial = None
        self.devices.store[self.device_id].update(control="idle", ownerRunId=None)


class FakeDeviceRepository:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self.store = store

    def list(self) -> list[dict[str, Any]]:
        return [dict(d) for d in self.store.values()]

    def save(self, device: dict[str, Any]) -> None:
        self.store[device["deviceId"]] = dict(device)


class FakeDevices:
    def __init__(self) -> None:
        self.store = {"dev-1": {"deviceId": "dev-1", "control": "idle", "ownerRunId": None}}
        self.repository = FakeDeviceRepository(self.store)
        self.contexts: list[FakeContext] = []
        self.connect_error = False

    def context(self, device_id: str) -> FakeContext:
        ctx = FakeContext(self, device_id)
        self.contexts.append(ctx)
        return ctx


class FakeModels:
    def __init__(self) -> None:
        self.error: ModelError | None = None
        self.kind, self.base_url = "openai-compatible", "http://localhost:8000/v1"

    def execution_binding(self, model_id: str) -> ModelExecutionBinding:
        if self.error:
            raise self.error
        return ModelExecutionBinding(model_id, "gpt-x", ProviderConnection("p", self.kind, self.base_url), SECRET)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    engine = create_engine(f"sqlite:///{tmp_path / 'ai.sqlite3'}")
    Base.metadata.create_all(engine)
    repo = RecordingRepository(sessionmaker(engine, expire_on_commit=False))
    tool, devices, models = FakeTool(), FakeDevices(), FakeModels()
    console: set[str] = set()
    external = [{"serial": "emulator-5554", "state": "device", "model": "Pixel", "product": "p"},
                {"serial": "offline-1", "state": "offline", "model": None, "product": None}]
    seen: list[set[str]] = []

    async def fake_list(managed: set[str], adb: Any = None) -> list[dict[str, Any]]:
        seen.append(set(managed))
        return [d for d in external if d["serial"] not in managed]

    monkeypatch.setattr(ai_tests, "list_external_devices", fake_list)
    service = AiTestService(repo, tool, devices, models, lambda: set(console), tmp_path / "artifacts")
    return {"service": service, "repo": repo, "tool": tool, "devices": devices, "models": models,
            "console": console, "seen": seen, "db": tmp_path / "ai.sqlite3"}


def request(n: int = 1, **extra: Any) -> dict[str, Any]:
    return {"requestId": f"req-{n}", "deviceKind": "managed", "deviceId": "dev-1", "instruction": "打开设置",
            "mode": "flash", "modelId": "m-1", "maxSteps": 5, "timeoutSeconds": 60, **extra}


def external(n: int = 1, serial: str = "emulator-5554") -> dict[str, Any]:
    return request(n, deviceKind="external", deviceId=None, serial=serial)


async def settle(service: AiTestService) -> None:
    await asyncio.gather(*list(service._tasks.values()), return_exceptions=True)


@pytest.mark.asyncio
async def test_managed_success_runs_and_cleans_up_once(env: dict[str, Any]) -> None:
    service, repo, tool, devices = env["service"], env["repo"], env["tool"], env["devices"]
    record = await service.start(request())
    assert record["state"] == "queued" and record["toolVersion"] == ARTEMIS_COMMIT and record["modelKey"] == "gpt-x"
    assert record["serial"] is None  # managed adb serials are never persisted
    await settle(service)
    final = repo.get(record["id"])
    assert final["state"] == "succeeded" and final["succeeded"] is True and final["traceId"] == "t-1"
    assert final["startedAt"] and final["finishedAt"]
    assert final["steps"] == [{"index": 1, "summary": "打开设置", "screenshot": "step-001.jpg"}]
    assert final["artifactsDir"].endswith(record["id"])
    (ctx,) = devices.contexts
    assert ctx.claims == [("dev-1", record["id"], "ai_test")] and ctx.cleanups == 1
    run = tool.runs[0]
    assert run["serial"] == "127.0.0.1:41234" and run["model"].secret == SECRET and run["max_steps"] == 5
    assert devices.store["dev-1"]["control"] == "idle"


@pytest.mark.asyncio
async def test_timeout_fails_with_code_and_still_cleans_up(env: dict[str, Any]) -> None:
    env["tool"].behaviour = "timeout"
    record = await env["service"].start(request())
    await settle(env["service"])
    final = env["repo"].get(record["id"])
    assert (final["state"], final["errorCode"]) == ("failed", "AI_TEST_TIMEOUT")
    assert "30 秒" in final["errorMessage"] and final["finishedAt"]
    assert env["devices"].contexts[0].cleanups == 1


@pytest.mark.asyncio
async def test_unexpected_crash_fails_internal_and_redacts_secret(env: dict[str, Any]) -> None:
    env["tool"].behaviour = "crash"
    record = await env["service"].start(request())
    await settle(env["service"])
    final = env["repo"].get(record["id"])
    assert (final["state"], final["errorCode"]) == ("failed", "AI_TEST_INTERNAL")
    assert "boom" in final["errorMessage"] and SECRET not in final["errorMessage"]
    assert env["devices"].contexts[0].cleanups == 1


@pytest.mark.asyncio
async def test_cancel_marks_cancelled(env: dict[str, Any]) -> None:
    service, tool = env["service"], env["tool"]
    tool.behaviour, tool.gate = "wait", asyncio.Event()
    record = await service.start(request())
    while not tool.runs:
        await asyncio.sleep(0.01)
    returned = await service.cancel(record["id"])
    assert returned["id"] == record["id"]
    await settle(service)
    final = env["repo"].get(record["id"])
    assert final["state"] == "cancelled" and final["finishedAt"]
    assert (await service.cancel(record["id"]))["state"] == "cancelled"  # terminal: unchanged
    with pytest.raises(AndroidError) as err:
        await service.cancel("missing")
    assert err.value.status == 404


@pytest.mark.asyncio
async def test_same_external_serial_is_busy_until_first_finishes(env: dict[str, Any]) -> None:
    service, tool = env["service"], env["tool"]
    tool.behaviour, tool.gate = "wait", asyncio.Event()
    first = await service.start(external(1))
    assert first["serial"] == "emulator-5554" and first["deviceKind"] == "external"
    with pytest.raises(AndroidError) as err:
        await service.start(external(2))
    assert (err.value.code, err.value.status) == ("AI_TEST_DEVICE_BUSY", 409)
    tool.gate.set()
    await settle(service)
    tool.behaviour = "succeed"
    again = await service.start(external(3))
    await settle(service)
    assert env["repo"].get(again["id"])["state"] == "succeeded"
    assert env["repo"].get(first["id"])["state"] == "succeeded"


@pytest.mark.asyncio
async def test_external_rejects_managed_and_offline_serials(env: dict[str, Any]) -> None:
    service, tool = env["service"], env["tool"]
    env["console"].add("127.0.0.1:5555")
    with pytest.raises(AndroidError) as err:
        await service.start(external(1, serial="127.0.0.1:5555"))
    assert (err.value.code, err.value.status) == ("AI_TEST_DEVICE_MANAGED", 409)
    # A serial the service itself is running on a managed device is also excluded.
    tool.behaviour, tool.gate = "wait", asyncio.Event()
    await service.start(request(2))
    with pytest.raises(AndroidError) as err:
        await service.start(external(3, serial="127.0.0.1:41234"))
    assert err.value.code == "AI_TEST_DEVICE_MANAGED"
    await service.external_devices()
    assert env["seen"][-1] == {"127.0.0.1:5555", "127.0.0.1:41234"}
    for serial in ("offline-1", "ghost"):
        with pytest.raises(AndroidError) as err:
            await service.start(external(4, serial=serial))
        assert (err.value.code, err.value.status) == ("AI_TEST_DEVICE_OFFLINE", 409)
    tool.gate.set()
    await settle(service)


@pytest.mark.asyncio
@pytest.mark.parametrize("case,code", [
    ("tool", "AI_TOOL_NOT_READY"),
    ("model_disabled", "MODEL_DISABLED"),
    ("model_kind", "AI_TEST_MODEL_UNSUPPORTED"),
    ("model_base_url", "AI_TEST_MODEL_UNSUPPORTED"),
    ("helper", "AI_TEST_HELPER_REQUIRED"),
    ("connect", "ANDROID_CONNECT_FAILED"),
])
async def test_pre_start_failures_leave_no_record_and_no_claim(env: dict[str, Any], case: str, code: str) -> None:
    service, tool, models, devices = env["service"], env["tool"], env["models"], env["devices"]
    if case == "tool":
        tool.state = "not_installed"
    elif case == "model_disabled":
        models.error = ModelError("MODEL_DISABLED", "所选模型已停用", 409)
    elif case == "model_kind":
        models.kind = "custom"
    elif case == "model_base_url":
        models.kind, models.base_url = "anthropic", "https://proxy.example.com/v1"
    elif case == "helper":
        tool.helper_installed = False
    else:
        devices.connect_error = True
    with pytest.raises(AndroidError) as err:
        await service.start(request())
    assert (err.value.code, err.value.status) == (code, 409 if code != "ANDROID_CONNECT_FAILED" else 502)
    if case == "model_disabled":
        assert err.value.message == "所选模型已停用"
    assert env["repo"].unfinished() == [] and env["repo"].get_by_request("req-1") is None
    assert devices.store["dev-1"]["control"] == "idle"
    for ctx in devices.contexts:  # every claim taken was released
        assert ctx.cleanups == len(ctx.claims)
    assert not tool.runs


@pytest.mark.asyncio
async def test_default_base_url_for_anthropic_is_supported(env: dict[str, Any]) -> None:
    env["models"].kind, env["models"].base_url = "anthropic", "https://api.anthropic.com/v1"
    record = await env["service"].start(request())
    await settle(env["service"])
    assert env["repo"].get(record["id"])["state"] == "succeeded"
    assert env["tool"].runs[0]["model"].base_url is None


@pytest.mark.asyncio
async def test_external_helper_missing_releases_lock(env: dict[str, Any]) -> None:
    env["tool"].helper_installed = False
    with pytest.raises(AndroidError) as err:
        await env["service"].start(external(1))
    assert err.value.code == "AI_TEST_HELPER_REQUIRED"
    assert await env["service"].install_helper("external", None, "emulator-5554") is True
    record = await env["service"].start(external(2))
    await settle(env["service"])
    assert env["repo"].get(record["id"])["state"] == "succeeded"


@pytest.mark.asyncio
async def test_install_helper_managed_claims_and_releases(env: dict[str, Any]) -> None:
    env["tool"].helper_installed = False
    assert await env["service"].install_helper("managed", "dev-1", None) is True
    (ctx,) = env["devices"].contexts
    assert ctx.claims[0][2] == "ai_test" and ctx.cleanups == 1
    assert env["tool"].helper_calls == [("127.0.0.1:41234", True)]


@pytest.mark.asyncio
async def test_same_request_id_is_idempotent(env: dict[str, Any]) -> None:
    service = env["service"]
    first = await service.start(request())
    await settle(service)
    again = await service.start(request())
    assert again["id"] == first["id"]
    assert len(env["devices"].contexts) == 1 and len(env["tool"].runs) == 1
    with pytest.raises(AndroidError) as err:
        await service.start(request(instruction="别的指令"))
    assert err.value.code == "ANDROID_REQUEST_CONFLICT"


@pytest.mark.asyncio
async def test_secret_never_written_to_repository(env: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    service, tool = env["service"], env["tool"]
    for n, behaviour in enumerate(("succeed", "crash", "timeout")):
        tool.behaviour = behaviour
        await service.start(request(n))
        await settle(service)
    assert env["repo"].writes and all(SECRET not in w for w in env["repo"].writes)
    assert SECRET.encode() not in env["db"].read_bytes()
    assert caplog.records and SECRET not in caplog.text


@pytest.mark.asyncio
async def test_recover_marks_unfinished_and_resets_ai_test_devices(env: dict[str, Any]) -> None:
    repo, devices = env["repo"], env["devices"]
    repo.create({"id": "r1", "requestId": "q1", "deviceKind": "managed", "deviceId": "dev-1", "serial": None,
                 "state": "running", "createdAt": "2026-10-01T00:00:00+00:00", "requestDigest": "d"})
    devices.store["dev-1"].update(control="ai_test", ownerRunId="r1")
    devices.store["dev-2"] = {"deviceId": "dev-2", "control": "workflow", "ownerRunId": "w1"}
    await env["service"].recover()
    final = repo.get("r1")
    assert final["state"] == "needs_verification"
    assert final["errorMessage"] == "程序中断，无法确定测试是否完成"
    assert devices.store["dev-1"]["control"] == "idle" and devices.store["dev-1"]["ownerRunId"] is None
    assert devices.store["dev-2"]["control"] == "workflow"


@pytest.mark.asyncio
async def test_shutdown_cancels_running_tasks(env: dict[str, Any]) -> None:
    service, tool = env["service"], env["tool"]
    tool.behaviour, tool.gate = "wait", asyncio.Event()
    record = await service.start(request())
    while not tool.runs:
        await asyncio.sleep(0.01)
    await service.shutdown()
    assert env["repo"].get(record["id"])["state"] == "cancelled"
    assert env["devices"].contexts[0].cleanups == 1 and not service._tasks


@pytest.mark.asyncio
async def test_install_tool_runs_once_at_a_time(env: dict[str, Any]) -> None:
    service, tool = env["service"], env["tool"]
    tool.state = "not_installed"
    first = await service.install_tool("i-1")
    second = await service.install_tool("i-2")
    assert first["state"] == second["state"] == "installing" and tool.installs == 1
    tool.install_gate.set()
    await service._install_task
    assert (await service.tool_status()).state == "ready"
