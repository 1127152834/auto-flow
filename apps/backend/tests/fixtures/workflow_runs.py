import asyncio
from pathlib import Path

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import ProfileSpec
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway


class InstalledLookup:
    def is_installed(self, _edition, _version):
        return True


class ControlledWorkflowWorker:
    def __init__(self):
        self.started = asyncio.Event()
        self.complete = asyncio.Event()
        self.cleanup = asyncio.Event()
        self.cleanup.set()
        self.cleaned = asyncio.Event()
        self.active = False
        self.stopped = False
        self.executions = 0
        self.artifact = None
        self.callback = None

    async def execute(self, run_id, prepared, profile, executable, proxy, license_key, on_event):
        self.active = True
        self.executions += 1
        self.callback = on_event
        self.arguments = (prepared, profile, executable, proxy, license_key)
        await on_event({"type": "ready", "message": "ready"})
        await on_event({"type": "node_started", "nodeId": prepared.node_ids[0], "message": "started"})
        self.started.set()
        await self.complete.wait()
        if not self.stopped:
            for node_id in prepared.node_ids:
                event = {"type": "node_succeeded", "nodeId": node_id, "message": "done", "durationMs": 12.5}
                if self.artifact is not None and node_id == self.artifact["nodeId"]:
                    event["artifact"] = self.artifact
                await on_event(event)
        await self.cleanup.wait()
        self.active = False
        self.cleaned.set()
        return {"state": "cancelled" if self.stopped else "succeeded", "error": None}

    async def stop(self, _run_id):
        if self.active:
            self.stopped = True
            self.complete.set()
            await self.cleaned.wait()

    async def shutdown(self):
        await self.stop("unused")

    def busy(self):
        return self.active


def workflow_runtime(tmp_path: Path):
    worker = ControlledWorkflowWorker()
    app = create_app(
        Settings(data_dir=str(tmp_path), instance_id="workflow-test", instance_token="renderer", host_token="host"),
        installed_kernel_lookup=InstalledLookup(), credential_store=FakeCredentialStore(),
        model_gateway=FakeModelGateway(), workflow_run_launcher=worker,
    )
    executable = tmp_path / "test-kernel"
    executable.touch()
    profile = app.state.profile_service.create(ProfileSpec.from_values({
        "name": "运行配置", "browser_version": "145.0.0.1", "start_url": "https://not-visited.invalid",
    }))
    app.state.workflow_run_service._installed_kernels = lambda: [InstalledKernel("public", "145.0.0.1", executable, 0)]
    return app, profile, worker


async def close_workflow_runtime(app):
    async with app.router.lifespan_context(app):
        pass
