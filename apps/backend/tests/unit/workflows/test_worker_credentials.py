from __future__ import annotations

import asyncio
import io
import json
from threading import Event, Thread

import pytest

from autoflow.providers.browser.workflow_worker import (
    _WorkerCommandBus,
    _WorkerCredentialReader,
)


@pytest.mark.asyncio
async def test_reader_reply_is_received_on_stdin_thread_while_event_loop_is_blocked():
    output = io.StringIO()
    bus = _WorkerCommandBus(
        asyncio.get_running_loop(), Event(), output, {"runId": "run"}
    )

    def reply():
        while not output.getvalue():
            Event().wait(0.001)
        request = json.loads(output.getvalue())
        bus.receive(
            {"type": "credential:result", "requestId": "wrong", "value": "wrong"}
        )
        bus.receive(
            {
                "type": "credential:result",
                "requestId": request["requestId"],
                "value": "actual",
            }
        )
        bus.receive(
            {
                "type": "credential:result",
                "requestId": request["requestId"],
                "value": "duplicate",
            }
        )

    thread = Thread(target=reply, daemon=True)
    thread.start()
    try:
        # Deliberately sync, just like ExecutionContext.resolve_value; no await can
        # process loop.call_soon callbacks until the response has arrived.
        assert bus.credentials.get_field("account", "value") == "actual"
        assert not bus.credentials._pending
    finally:
        bus.close()
        thread.join(1)


@pytest.mark.parametrize("kind", ["stop", "eof"])
def test_stop_and_parent_eof_interrupt_credential_wait(kind):
    output, stopped = io.StringIO(), Event()
    reader = _WorkerCredentialReader(stopped, output, "run")

    def cancel():
        while not output.getvalue():
            Event().wait(0.001)
        stopped.set() if kind == "stop" else reader.close()

    thread = Thread(target=cancel, daemon=True)
    thread.start()
    try:
        with pytest.raises(asyncio.CancelledError):
            reader.get_field("account", "value")
        assert not reader._pending
    finally:
        reader.close()
        thread.join(1)


def test_timeout_drops_late_secret_and_pending_reference(monkeypatch):
    now = iter([0, 10])
    monkeypatch.setattr(
        "autoflow.providers.browser.workflow_worker.monotonic", lambda: next(now)
    )
    output = io.StringIO()
    reader = _WorkerCredentialReader(Event(), output, "run")
    with pytest.raises(TimeoutError):
        reader.get_field("account", "value")
    request = json.loads(output.getvalue())
    reader.receive({"requestId": request["requestId"], "value": "late"})
    assert not reader._pending
    assert "late" not in output.getvalue()


@pytest.mark.asyncio
async def test_stopping_worker_drops_secret_reply_queued_behind_write_lock(tmp_path):
    from types import SimpleNamespace

    from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager

    writes = []

    class Input:
        def is_closing(self):
            return False

        def write(self, value):
            writes.append(value)

        async def drain(self):
            pass

    lock = asyncio.Lock()
    await lock.acquire()
    manager = WorkflowWorkerManager(tmp_path)
    manager._running["run"] = SimpleNamespace(
        process=SimpleNamespace(returncode=None, stdin=Input()), write_lock=lock
    )
    task = asyncio.create_task(
        manager.send_command(
            "run", {"type": "credential:result", "value": "must-not-write"}
        )
    )
    try:
        await asyncio.sleep(0)
        manager._stopping.add("run")
        lock.release()
        await task
        assert writes == []
    finally:
        task.cancel()
        manager._running.clear()
