"""Opt-in CI diagnostics: protocol kinds and process exit status, never payloads."""
import logging
import os

import pytest

from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)


@pytest.fixture(autouse=True)
def project_worker_diagnostics(monkeypatch):
    if os.environ.get("AUTOFLOW_TEST_WORKER_DIAGNOSTICS") != "1":
        return
    logger = logging.getLogger("pm9.worker_probe")
    read = ProjectWorkflowWorkerManager._read
    send = ProjectWorkflowWorkerManager._send
    capability = ProjectWorkflowWorkerManager._capability_while_alive

    async def observed_read(self, worker):
        try:
            message = await read(self, worker)
        except BaseException as error:
            logger.warning("read failed: type=%s code=%s ready=%s exit=%s", type(error).__name__, getattr(error, "code", None), worker.ready, worker.process.returncode)
            raise
        logger.warning("received: type=%s kind=%s operation=%s", message.get("type"), message.get("event", {}).get("kind"), message.get("operation"))
        return message

    async def observed_send(self, worker, message):
        logger.warning("sending: type=%s exit=%s", message.get("type"), worker.process.returncode)
        return await send(self, worker, message)

    async def observed_capability(self, worker, message):
        try:
            return await capability(self, worker, message)
        except BaseException as error:
            logger.warning("capability failed: type=%s code=%s exit=%s", type(error).__name__, getattr(error, "code", None), worker.process.returncode)
            raise

    monkeypatch.setattr(ProjectWorkflowWorkerManager, "_read", observed_read)
    monkeypatch.setattr(ProjectWorkflowWorkerManager, "_send", observed_send)
    monkeypatch.setattr(ProjectWorkflowWorkerManager, "_capability_while_alive", observed_capability)
