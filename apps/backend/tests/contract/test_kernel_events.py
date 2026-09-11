import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from autoflow.adapters.events.kernels import kernel_event_stream
from autoflow.application.kernels.operations import KernelOperation
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.events.kernel_events import KernelEventBroker


def _operation(state: str = "downloading", progress: int | None = None) -> KernelOperation:
    operation = KernelOperation.new(
        operation_id="operation-1",
        edition="public",
        requested_version="146.0.7680.80",
        release_channel="stable",
        state="queued",
    )
    if state != "queued":
        from autoflow.application.kernels.operations import transition_operation

        operation = transition_operation(operation, state, progress=progress)
    return operation


def _data(frame: str) -> dict[str, object]:
    line = next(line for line in frame.splitlines() if line.startswith("data: "))
    return json.loads(line.removeprefix("data: "))


@pytest.mark.asyncio
async def test_sse_connection_starts_with_full_snapshot_and_indeterminate_progress() -> None:
    broker = KernelEventBroker()
    stream = kernel_event_stream(
        broker,
        snapshot=lambda: [_operation(progress=None)],
        heartbeat_interval=0.01,
    )

    first = await anext(stream)
    payload = _data(first)

    assert payload["type"] == "snapshot"
    assert payload["operations"][0]["progress"] is None
    await stream.aclose()


@pytest.mark.asyncio
async def test_sse_heartbeat_is_emitted_while_idle() -> None:
    stream = kernel_event_stream(
        KernelEventBroker(), snapshot=list, heartbeat_interval=0.01
    )
    await anext(stream)
    assert await anext(stream) == ": heartbeat\n\n"
    await stream.aclose()


@pytest.mark.asyncio
async def test_reconnected_sse_reads_a_fresh_snapshot() -> None:
    broker = KernelEventBroker()
    current = [_operation(progress=10)]
    first = kernel_event_stream(broker, snapshot=lambda: current)
    assert _data(await anext(first))["operations"][0]["progress"] == 10
    await first.aclose()

    current = [_operation(progress=62)]
    reconnected = kernel_event_stream(broker, snapshot=lambda: current)
    assert _data(await anext(reconnected))["operations"][0]["progress"] == 62
    await reconnected.aclose()


@pytest.mark.asyncio
async def test_backpressure_keeps_latest_snapshot_and_terminal_state() -> None:
    broker = KernelEventBroker(queue_size=1)
    subscription = broker.subscribe()
    broker.publish([_operation(progress=10)])
    broker.publish([_operation(progress=62)])
    terminal = _operation()
    from autoflow.application.kernels.operations import transition_operation

    terminal = transition_operation(terminal, "cancelling")
    terminal = transition_operation(terminal, "cancelled")
    broker.publish([terminal])

    latest = await asyncio.wait_for(subscription.queue.get(), timeout=0.1)
    assert latest[0].state == "cancelled"
    subscription.close()


def test_kernel_events_requires_instance_token(tmp_path) -> None:
    client = TestClient(
        create_app(
            Settings(data_dir=str(tmp_path), instance_id="test", instance_token="secret")
        )
    )

    assert client.get("/api/v1/kernels/events").status_code == 401
