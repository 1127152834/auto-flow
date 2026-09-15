from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.executors.base import ModuleExecutor
from autoflow.application.workflows.executors.basic import OpenPageExecutor
from autoflow.application.workflows.executors.data_structure import StringConcatExecutor
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.errors import KernelNotInstalled, ProfileNotFound
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.browser import WorkflowWorkerSession
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments


class Resources:
    def __init__(self) -> None:
        self.owner_id: str | None = None
        self.acquired: list[str] = []
        self.released: list[str] = []

    async def acquire(self, owner_id: str, _profile_id: str, _kernel: Any) -> None:
        self.owner_id = owner_id
        self.acquired.append(owner_id)

    async def release(self, owner_id: str) -> None:
        assert self.owner_id == owner_id
        self.owner_id = None
        self.released.append(owner_id)


class Workers:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.started = 0
        self.stopped: list[str] = []
        self.executables: list[Path | None] = []
        self.payloads: list[dict[str, Any]] = []

    async def start(
        self,
        run_id: str,
        profile_id: str,
        executable: Path | None,
        payload: dict[str, Any],
    ) -> WorkflowWorkerSession:
        self.started += 1
        self.executables.append(executable)
        self.payloads.append(payload)
        if self.failure is not None:
            raise self.failure
        return WorkflowWorkerSession(run_id, profile_id, 10, 11)

    async def stop(self, run_id: str) -> None:
        self.stopped.append(run_id)

    def busy(self) -> bool:
        return self.started > 0 and self.failure is None and not self.stopped


class Profiles:
    def __init__(self, profile: Profile | None) -> None:
        self.profile = profile

    def get(self, profile_id: str) -> Profile:
        if self.profile is None or self.profile.id != profile_id:
            raise ProfileNotFound(profile_id)
        return self.profile


def profile(*, edition: str = "public") -> Profile:
    spec = ProfileSpec.from_values(
        {
            "name": "准入测试配置",
            "description": "",
            "start_url": "about:blank",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "geoip": False,
            "headless": False,
            "humanize": True,
            "human_preset": "default",
            "user_agent": "AutoFlow",
            "viewport": {"width": 1280, "height": 720},
            "color_scheme": "dark",
            "extension_paths": [],
            "expert_args": [],
            "browser_version": "145.0.1",
            "browser_edition": edition,
            "release_channel": "stable",
            "proxy_mode": "none",
        }
    )
    now = datetime(2026, 9, 15, tzinfo=UTC)
    return Profile("profile-admission", spec, 123, now, now)


def coordinator(
    tmp_path: Path,
    *,
    selected_profile: Profile | None,
    kernels: list[InstalledKernel],
    resources: Resources,
    workers: Workers,
    resolve_proxy: Any | None = None,
    read_license: Any | None = None,
    module_type: str = "open_page",
    module_config: dict[str, Any] | None = None,
    executor_class: type[ModuleExecutor] = OpenPageExecutor,
) -> tuple[WorkflowRunCoordinator, WorkflowRunService]:
    database = tmp_path / "admission.sqlite3"
    migrate_database(database)
    sessions = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(sessions))
    documents.create(
        {
            "id": "workflow-admission",
            "name": "运行准入",
            "nodes": [
                {
                    "id": "open",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": module_type,
                        "config": module_config or {"url": "about:blank"},
                    },
                }
            ],
            "edges": [],
            "variables": [],
        },
        client_request_id="create-admission",
    )
    repository = SqlAlchemyWorkflowRuns(sessions)
    runs = WorkflowRunService(repository)
    registry = ExecutorRegistry()
    registry.register(executor_class)

    async def no_proxy(_profile: Profile, _run_id: str) -> None:
        return None

    return (
        WorkflowRunCoordinator(
            documents=documents,
            runs=runs,
            run_repository=repository,
            runtime=WorkflowRuntime(registry),
            profiles=Profiles(selected_profile),
            installed_kernels=lambda: kernels,
            resolve_proxy=resolve_proxy or no_proxy,
            read_license=read_license or (lambda: None),
            workers=workers,
            resources=resources,
            events=StudioEventJournal(),
            artifact_root=tmp_path / "workspace",
        ),
        runs,
    )


def request() -> dict[str, Any]:
    return {
        "runId": "run-admission",
        "documentId": "document-admission",
        "profileId": "profile-admission",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["profile", "kernel"])
async def test_missing_profile_or_kernel_creates_no_run_or_resource_lease(
    tmp_path: Path, missing: str
) -> None:
    selected = None if missing == "profile" else profile()
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    kernels = (
        []
        if missing == "kernel"
        else [InstalledKernel("public", "145.0.1", executable, executable.stat().st_size)]
    )
    resources = Resources()
    workers = Workers()
    service, runs = coordinator(
        tmp_path,
        selected_profile=selected,
        kernels=kernels,
        resources=resources,
        workers=workers,
    )

    expected = ProfileNotFound if missing == "profile" else KernelNotInstalled
    with pytest.raises(expected):
        await service.start("workflow-admission", request())

    with pytest.raises(WorkflowRunError) as missing_run:
        runs.get("run-admission")
    assert missing_run.value.code == "RUN_NOT_FOUND"
    assert resources.acquired == resources.released == []
    assert workers.started == 0


@pytest.mark.asyncio
async def test_missing_license_releases_resources_and_records_failed_start(
    tmp_path: Path,
) -> None:
    selected = profile(edition="licensed")
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    resources = Resources()
    workers = Workers()
    service, runs = coordinator(
        tmp_path,
        selected_profile=selected,
        kernels=[InstalledKernel("licensed", "145.0.1", executable, 6)],
        resources=resources,
        workers=workers,
    )

    with pytest.raises(LicenseInvalid):
        await service.start("workflow-admission", request())

    run = runs.get("run-admission")
    assert run.status == "failed"
    assert run.cleanup_state == "completed"
    assert run.error == {
        "code": "LICENSE_INVALID",
        "message": "CloakBrowser license is invalid or expired",
    }
    assert resources.acquired == resources.released == ["run-admission"]
    assert resources.owner_id is None
    assert workers.started == 0


@pytest.mark.asyncio
async def test_pure_data_run_does_not_require_kernel_license_proxy_or_browser_lock(
    tmp_path: Path,
) -> None:
    resources = Resources()
    workers = Workers()

    async def forbidden_proxy(_profile: Profile, _run_id: str) -> None:
        raise AssertionError("pure data run must not resolve a browser proxy")

    def forbidden_license() -> str | None:
        raise AssertionError("pure data run must not read the CloakBrowser License")

    service, _runs = coordinator(
        tmp_path,
        selected_profile=profile(edition="licensed"),
        kernels=[],
        resources=resources,
        workers=workers,
        resolve_proxy=forbidden_proxy,
        read_license=forbidden_license,
        module_type="string_concat",
        module_config={
            "string1": "Auto",
            "string2": "Flow",
            "variableName": "joined",
        },
        executor_class=StringConcatExecutor,
    )

    started = await service.start("workflow-admission", request())

    assert started["status"] == "running"
    assert resources.acquired == []
    assert workers.executables == [None]
    assert workers.payloads[0]["requiresBrowser"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["proxy", "worker"])
async def test_start_failure_releases_resources_and_does_not_leave_a_starting_run(
    tmp_path: Path, failure_stage: str
) -> None:
    selected = profile()
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    resources = Resources()
    workers = Workers(
        failure=RuntimeError("worker failed") if failure_stage == "worker" else None
    )

    async def proxy_failure(_profile: Profile, _run_id: str) -> None:
        raise RuntimeError("proxy failed")

    service, runs = coordinator(
        tmp_path,
        selected_profile=selected,
        kernels=[InstalledKernel("public", "145.0.1", executable, 6)],
        resources=resources,
        workers=workers,
        resolve_proxy=proxy_failure if failure_stage == "proxy" else None,
    )

    with pytest.raises(WorkflowRunError) as caught:
        await service.start("workflow-admission", request())

    assert caught.value.code == "RUN_START_FAILED"
    run = runs.get("run-admission")
    assert run.status == "failed"
    assert run.cleanup_state == "completed"
    assert resources.acquired == resources.released == ["run-admission"]
    assert resources.owner_id is None
    assert workers.started == (1 if failure_stage == "worker" else 0)


@pytest.mark.asyncio
async def test_worker_crash_marks_run_failed_without_replay_and_releases_resources(
    tmp_path: Path,
) -> None:
    selected = profile()
    executable = tmp_path / "CloakBrowser"
    executable.write_bytes(b"kernel")
    resources = Resources()
    workers = Workers()
    service, runs = coordinator(
        tmp_path,
        selected_profile=selected,
        kernels=[InstalledKernel("public", "145.0.1", executable, 6)],
        resources=resources,
        workers=workers,
    )

    started = await service.start("workflow-admission", request())
    await service.on_worker_exit("run-admission", 17)

    failed = runs.get("run-admission")
    assert started["status"] == "running"
    assert failed.status == "failed"
    assert failed.cleanup_state == "completed"
    assert failed.error == {
        "code": "WORKFLOW_EXECUTION_FAILED",
        "message": "工作流执行失败",
    }
    assert workers.started == 1
    assert workers.stopped == []
    assert resources.acquired == resources.released == ["run-admission"]
    assert resources.owner_id is None
    assert [event.type for event in runs.events("run-admission", limit=20)] == [
        "execution:running",
        "execution:log",
        "execution:failed",
    ]
