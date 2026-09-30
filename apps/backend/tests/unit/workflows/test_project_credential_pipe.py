from __future__ import annotations

import asyncio
import io
import json
import os
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from autoflow.providers.browser.project_workflow_worker import _Input
from autoflow.providers.browser.workflow_worker import _WorkerCredentialReader


@pytest.mark.parametrize("operation", ["reply", "stop", "eof", "wrong-generation"])
def test_stdin_thread_resolves_or_cancels_without_async_reader(operation):
    read_fd, write_fd = os.pipe()
    source, destination = os.fdopen(read_fd), os.fdopen(write_fd, "w")
    output = io.StringIO()
    reader = _WorkerCredentialReader(Event(), output, "run", protocol_metadata={"protocolVersion": 1, "executionGeneration": 3})
    incoming = _Input(source)
    incoming.credentials, incoming.generation = reader, 3
    incoming.start()

    def respond():
        while not output.getvalue():
            Event().wait(.001)
        request = json.loads(output.getvalue())
        assert request["executionGeneration"] == 3
        if operation == "eof":
            destination.close()
            return
        reply = {**request, "type": "credential:result", "value": "actual-private-value"}
        if operation == "stop":
            reply = {"type": "stop", "executionGeneration": 3}
        elif operation == "wrong-generation":
            reply["executionGeneration"] = 2
        else:
            # Foreign run, unknown identity and duplicate replies never replace
            # the first valid response, even while the main thread is blocked.
            for update in ({"runId": "other"}, {"requestId": "unknown"}):
                destination.write(json.dumps({**reply, **update, "value": "wrong"}) + "\n")
        destination.write(json.dumps(reply) + "\n")
        if operation == "reply":
            destination.write(json.dumps({**reply, "value": "duplicate"}) + "\n")
        destination.flush()

    thread = Thread(target=respond, daemon=True)
    thread.start()
    try:
        if operation == "reply":
            assert reader.get_field("account", "password") == "actual-private-value"
        else:
            with pytest.raises(asyncio.CancelledError):
                reader.get_field("account", "password")
        assert not reader._pending
        assert "actual-private-value" not in output.getvalue()
    finally:
        thread.join(1)
        reader.close()
        destination.close()
        source.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["stop", "replaced", "cleanup"])
async def test_queued_secret_reply_is_discarded_after_owner_changes(tmp_path, state):
    writes = []

    class Input:
        def write(self, value):
            writes.append(value)

        async def drain(self):
            pass

    lock = asyncio.Lock()
    await lock.acquire()
    worker = SimpleNamespace(run_id="run", write_lock=lock, stop_requested=False, cleanup=None, process=SimpleNamespace(returncode=None, stdin=Input()))
    manager = ProjectWorkflowWorkerManager(tmp_path)
    manager._workers[worker.run_id] = worker
    pending = asyncio.create_task(manager._send(worker, {"type": "credential:result", "value": "do-not-write"}))
    await asyncio.sleep(0)
    if state == "stop":
        worker.stop_requested = True
    elif state == "cleanup":
        worker.cleanup = asyncio.current_task()
    else:
        manager._workers.pop(worker.run_id)
    lock.release()
    await pending
    assert writes == []
