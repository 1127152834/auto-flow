import asyncio
from types import SimpleNamespace

import pytest

from autoflow.application.proxies.usage import ProxyUsage
from autoflow.application.workflows.executors.proxy_control import ProxyChangeIPExecutor
from autoflow.domain.proxies.errors import ProxyInUseError
from autoflow.domain.workflows.execution import ExecutionContext


def projection(name="p"):
    return SimpleNamespace(id=name, connection_id="c", provider_id="remote", revision=1)


def test_usage_groups_remote_identity_and_requires_unique_owner():
    usage = ProxyUsage()
    usage.bind("one", projection())
    usage.bind("two", projection("alias"))
    with pytest.raises(ProxyInUseError):
        usage.claim(projection(), "one", "visit")
    usage.release("two")
    usage.claim(projection(), "one", "visit")
    with pytest.raises(ProxyInUseError):
        usage.bind("two", projection())
    with pytest.raises(ProxyInUseError):
        usage.check(projection(), None)
    usage.unclaim("visit")
    usage.release("one")
    usage.check(projection(), None)


class Gateway:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    async def __call__(self, payload):
        self.calls.append(dict(payload))
        if payload["method"] == "prepare":
            return {
                "proxyId": "p",
                "current": False,
                "before": {"exitIp": "8.8.8.8"},
                "targetLocation": None,
            }
        if payload["method"] == "attempt":
            return next(self.results)
        return {}


def result(ip="8.8.8.8", status="succeeded", sent=1):
    return {
        "status": status,
        "operationId": "op",
        "requestsSent": sent,
        "after": {"exitIp": ip, "source": "local_probe"},
        "error": None,
    }


@pytest.mark.asyncio
async def test_retries_fixed_baseline_then_succeeds(monkeypatch):
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(
        "autoflow.application.workflows.executors.proxy_control._sleep", sleep
    )
    gateway = Gateway([result(), result(), result("1.1.1.1")])
    context = ExecutionContext(proxy_control=gateway)
    output = await ProxyChangeIPExecutor().execute(
        {"resultVariable": "change"}, context
    )
    assert output.success
    assert context.variables["change"]["attemptsUsed"] == 3
    assert context.variables["change"]["before"]["exitIp"] == "8.8.8.8"
    assert context.variables["change"]["requestsSent"] == 3
    assert waits == [10, 10]
    assert gateway.calls[-1]["method"] == "finish"


@pytest.mark.asyncio
async def test_exhaustion_captures_result_and_never_sends_sixth(monkeypatch):
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(
        "autoflow.application.workflows.executors.proxy_control._sleep", sleep
    )
    gateway = Gateway([result()] * 5)
    context = ExecutionContext(
        proxy_control=gateway, variables={"change": {"status": "succeeded"}}
    )
    output = await ProxyChangeIPExecutor().execute(
        {"resultVariable": "change", "failureMode": "capture"}, context
    )
    assert output.success
    assert output.data["status"] == "failed"
    assert output.data["error"]["code"] == "PROXY_IP_SWITCH_FAILED"
    assert output.data["error"]["lastCode"] == "PROXY_IP_UNCHANGED"
    assert len(waits) == 4
    assert len([c for c in gateway.calls if c["method"] == "attempt"]) == 5


@pytest.mark.asyncio
async def test_invalid_configuration_cannot_reuse_previous_success():
    gateway = Gateway([])
    context = ExecutionContext(
        proxy_control=gateway, variables={"change": {"status": "succeeded"}}
    )
    output = await ProxyChangeIPExecutor().execute(
        {"resultVariable": "change", "maxAttempts": True}, context
    )
    assert not output.success
    assert context.variables["change"]["status"] == "failed"
    assert not gateway.calls


@pytest.mark.asyncio
async def test_unknown_preserves_operation_for_next_round(monkeypatch):
    async def sleep(seconds):
        pass

    monkeypatch.setattr(
        "autoflow.application.workflows.executors.proxy_control._sleep", sleep
    )
    gateway = Gateway([result(status="unknown"), result("1.1.1.1", sent=0)])
    output = await ProxyChangeIPExecutor().execute(
        {}, ExecutionContext(proxy_control=gateway)
    )
    assert output.success
    attempts = [c for c in gateway.calls if c["method"] == "attempt"]
    assert attempts[1]["operationId"] == "op"
    assert output.data["requestsSent"] == 1


@pytest.mark.asyncio
async def test_cancellation_is_not_captured(monkeypatch):
    async def sleep(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "autoflow.application.workflows.executors.proxy_control._sleep", sleep
    )
    gateway = Gateway([result()])
    with pytest.raises(asyncio.CancelledError):
        await ProxyChangeIPExecutor().execute(
            {"failureMode": "capture"}, ExecutionContext(proxy_control=gateway)
        )
    assert gateway.calls[-1]["method"] == "finish"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid", [0, -1, float("inf"), float("nan"), True, [], {}, "{missing}", "1.5"]
)
async def test_invalid_attempt_values_never_reach_host(invalid):
    gateway = Gateway([])
    output = await ProxyChangeIPExecutor().execute(
        {"maxAttempts": invalid}, ExecutionContext(proxy_control=gateway)
    )
    assert not output.success and not gateway.calls


@pytest.mark.asyncio
async def test_variables_are_frozen_and_one_attempt_does_not_wait(monkeypatch):
    async def forbidden_sleep(_seconds):
        pytest.fail("maxAttempts=1 must not sleep")

    monkeypatch.setattr(
        "autoflow.application.workflows.executors.proxy_control._sleep", forbidden_sleep
    )
    gateway = Gateway([result()])
    context = ExecutionContext(
        proxy_control=gateway,
        variables={"tries": 1, "delay": 0.5, "budget": 2, "proxy": "p"},
    )
    output = await ProxyChangeIPExecutor().execute(
        {
            "target": "specified",
            "proxyId": "{proxy}",
            "maxAttempts": "{tries}",
            "retryIntervalSeconds": "{delay}",
            "confirmationTimeoutSeconds": "{budget}",
        },
        context,
    )
    assert not output.success
    assert output.data["configuration"]["maxAttempts"] == 1
    assert output.data["configuration"]["retryIntervalSeconds"] == 0.5
    assert output.data["configuration"]["proxyId"] == "p"


@pytest.mark.asyncio
async def test_missing_current_baseline_is_capturable_and_sends_nothing():
    class Current(Gateway):
        async def __call__(self, value):
            result = await super().__call__(value)
            if value["method"] == "prepare":
                result["current"] = True
            return result

    gateway = Current([])

    async def probe(_reset):
        return {"exitIp": None, "error": "probe_failed"}

    context = ExecutionContext(proxy_control=gateway, proxy_probe=probe)
    result_value = await ProxyChangeIPExecutor().execute(
        {"failureMode": "capture"}, context
    )
    assert result_value.success
    assert result_value.data["status"] == "failed"
    assert result_value.data["error"]["lastCode"] == "PROXY_PROBE_FAILED"
    assert not [c for c in gateway.calls if c["method"] == "attempt"]


@pytest.mark.asyncio
async def test_parallel_browser_conflict_uses_complete_captured_result():
    context = ExecutionContext(proxy_activity={"browser-node"})
    result_value = await ProxyChangeIPExecutor().execute(
        {"failureMode": "capture"}, context
    )
    assert result_value.success and result_value.data["requestsSent"] == 0
    assert result_value.data["error"]["lastCode"] == "PROXY_BUSY"
    assert result_value.data == context.variables["proxy_change_ip_result"]


@pytest.mark.asyncio
async def test_captured_failure_does_not_poison_runtime_and_next_node_can_read_result(
    monkeypatch,
):
    from autoflow.application.workflows.executors.production import (
        build_production_executor_registry,
    )
    from autoflow.application.workflows.runtime import WorkflowRuntime

    gateway = Gateway([result()])
    context = ExecutionContext(proxy_control=gateway)
    document = {
        "nodes": [
            {
                "id": "proxy",
                "data": {
                    "moduleType": "proxy_change_ip",
                    "target": "specified",
                    "proxyId": "p",
                    "maxAttempts": 1,
                    "failureMode": "capture",
                    "resultVariable": "result",
                },
            },
            {
                "id": "after",
                "data": {
                    "moduleType": "set_variable",
                    "variableName": "observed",
                    "variableValue": "{result['status']}",
                },
            },
        ],
        "edges": [{"id": "e", "source": "proxy", "target": "after"}],
    }
    runtime = WorkflowRuntime(build_production_executor_registry())
    assert not runtime.requires_browser(document)
    run = await runtime.execute(document, context)
    assert run.success
    assert context.variables["observed"] == "failed"
    assert gateway.calls[0]["nodeId"] == "proxy" and gateway.calls[0]["executionId"]


def test_unconfirmed_legacy_owner_blocks_bindings_and_writes():
    usage = ProxyUsage()
    proxy = SimpleNamespace(connection_id="conn", provider_id="remote", id="local")
    usage.unconfirmed_users = lambda: True
    with pytest.raises(ProxyInUseError):
        usage.bind("owner", proxy)
    with pytest.raises(ProxyInUseError):
        usage.check(proxy, None)


@pytest.mark.asyncio
async def test_current_proxy_uses_browser_initialized_after_context_creation():
    gateway = Gateway([result("1.1.1.1")])
    async def control(payload):
        value = await gateway(payload)
        if payload["method"] == "prepare":
            value["current"] = True
        return value
    probes = []
    async def probe(reset=False):
        probes.append(reset)
        return {"exitIp": "1.1.1.1" if reset else "8.8.8.8", "source": "session_relay"}
    context = ExecutionContext(proxy_control=control)
    context.browser = SimpleNamespace(probe_proxy=probe)
    outcome = await ProxyChangeIPExecutor().execute({"maxAttempts": 1}, context)
    assert outcome.success
    assert probes == [False, True]
