from __future__ import annotations

from datetime import UTC, datetime

import pytest
from autoflow.application.workflows.inspection import WorkflowInspectionService
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.browser import WorkflowBrowserBusy
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database import workflow_recordings
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import WorkflowRecordingSessionRow
from autoflow.infrastructure.database.workflow_recordings import (
    SqlAlchemyWorkflowRecordings,
)


class Profiles:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def get(self, profile_id: str) -> Profile:
        assert profile_id == self.profile.id
        return self.profile


class Resources:
    owner_id: str | None = None

    async def acquire(self, owner_id, _profile_id, _kernel) -> None:
        if self.owner_id is not None:
            raise WorkflowBrowserBusy("busy")
        self.owner_id = owner_id

    async def release(self, owner_id) -> None:
        assert self.owner_id == owner_id
        self.owner_id = None


class Workers:
    def __init__(self) -> None:
        self.running = False
        self.service: WorkflowInspectionService | None = None
        self.session_id = ""
        self.commands: list[dict] = []
        self.recorded: list[dict] = []

    async def start(self, session_id, _profile_id, _executable, _payload) -> None:
        self.running = True
        self.session_id = session_id

    async def send_command(self, _session_id, command) -> None:
        self.commands.append(command)
        action = command["command"]
        data = {
            "pages": {
                "revision": 1,
                "targetPageId": "page-1",
                "pages": [{"pageId": "page-1", "title": "测试", "url": "https://example.test"}],
            },
            "start_picker": {"active": True},
            "stop_picker": {"active": False},
            "picker_result": {"selected": True, "value": {"selector": "#target", "tagName": "BUTTON"}},
            "test_selector": {"success": True, "matched": True, "count": 1, "tried": []},
            "recorder_start": {"recording": True, "events": []},
            "recorder_resume": {"recording": True, "paused": False, "events": []},
        }.get(action, {"success": True})
        if action in {"recorder_events", "recorder_pause", "recorder_stop"}:
            data = {
                "recording": action == "recorder_events",
                "paused": action == "recorder_pause",
                "events": self._drain_recorded(),
            }
        assert self.service is not None
        await self.service.on_worker_event(
            {
                "type": "inspection:response",
                "runId": self.session_id,
                "requestId": command["requestId"],
                "success": True,
                "data": data,
            }
        )

    async def stop(self, session_id) -> None:
        self.running = False
        assert self.service is not None
        await self.service.on_worker_exit(session_id, 0)

    async def shutdown(self) -> None:
        self.running = False

    def busy(self) -> bool:
        return self.running

    def _drain_recorded(self) -> list[dict]:
        events, self.recorded = self.recorded, []
        return events


def profile() -> Profile:
    now = datetime.now(UTC)
    spec = ProfileSpec.from_values(
        {
            "name": "检查配置",
            "start_url": "about:blank",
            "browser_version": "146.0.1.1",
            "browser_edition": "public",
            "release_channel": "stable",
            "geoip": False,
            "headless": True,
            "humanize": False,
            "human_preset": "default",
            "extension_paths": [],
            "expert_args": [],
            "proxy_mode": "none",
        }
    )
    return Profile("profile-1", spec, 12345, now, now)


@pytest.mark.asyncio
async def test_inspection_session_is_idempotent_and_releases_owned_resources(tmp_path):
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    resources = Resources()
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [
            InstalledKernel("public", "146.0.1.1", executable, 1)
        ],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=resources,  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
    )
    workers.service = service

    opened = await service.open(profile_id="profile-1")
    assert opened["isOpen"] is True
    assert resources.owner_id == opened["sessionId"]
    assert (await service.pages())["pages"][0]["title"] == "测试"

    first = await service.start_picker(
        session_id="picker-1", profile_id="profile-1", url=None
    )
    second = await service.start_picker(
        session_id="picker-1", profile_id="profile-1", url=None
    )
    assert first == second == {
        "success": True,
        "sessionId": "picker-1",
        "active": True,
        "selected": False,
    }
    assert [item["command"] for item in workers.commands].count("start_picker") == 1
    assert (await service.picker_result("picker-1", similar=False))["element"]["selector"] == "#target"
    assert (await service.test_selector({"selector": "#target", "sessionId": "picker-1"}))["count"] == 1

    await service.stop_picker("picker-1")
    await service.close(opened["sessionId"])
    assert resources.owner_id is None
    assert service.busy() is False


@pytest.mark.asyncio
async def test_picker_identity_conflicts_do_not_mutate_the_active_session(tmp_path):
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", executable, 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=Resources(),  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
    )
    workers.service = service
    await service.start_picker(session_id="picker-1", profile_id="profile-1", url=None)

    with pytest.raises(WorkflowRunError) as reused:
        await service.start_picker(
            session_id="picker-1", profile_id="profile-1", url="https://other.test"
        )
    assert reused.value.status == 409
    with pytest.raises(WorkflowRunError):
        await service.stop_picker("other")
    assert service.picker_status("picker-1")["active"] is True

    await service.stop_picker("picker-1")
    assert (await service.stop_picker("picker-1"))["active"] is False
    await service.close()


@pytest.mark.asyncio
async def test_inspection_rejects_an_existing_run_without_releasing_its_lock(tmp_path):
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    resources = Resources()
    resources.owner_id = "active-workflow-run"
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", executable, 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=resources,  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
    )
    workers.service = service

    with pytest.raises(WorkflowRunError) as busy:
        await service.open(profile_id="profile-1")
    assert busy.value.status == 409
    assert busy.value.code == "INSPECTION_SESSION_CONFLICT"
    assert resources.owner_id == "active-workflow-run"
    assert workers.running is False


@pytest.mark.asyncio
async def test_recording_uses_the_open_browser_and_persists_non_destructive_events(tmp_path):
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", executable, 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=Resources(),  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
        recordings=SqlAlchemyWorkflowRecordings(factory),
    )
    workers.service = service
    opened = await service.open(profile_id="profile-1")

    assert await service.start_recording("record-1") == {
        "success": True,
        "sessionId": "record-1",
        "recording": True,
        "paused": False,
        "nextSeq": 0,
    }
    workers.recorded.append(
        {"type": "input", "selector": "#name", "value": "中文"}
    )
    first = await service.recording_events("record-1", after_seq=0)
    second = await service.recording_events("record-1", after_seq=0)
    assert first == second == {
        "success": True,
        "sessionId": "record-1",
        "nextSeq": 1,
        "hasMore": False,
        "data": [
            {
                "sequence": 1,
                "type": "input",
                "selector": "#name",
                "value": "中文",
            }
        ],
    }

    with pytest.raises(WorkflowRunError, match="请先停止录制"):
        await service.close(opened["sessionId"])
    stopped = await service.stop_recording("record-1", after_seq=0)
    assert stopped["recording"] is False
    assert stopped["data"]["events"] == first["data"]
    assert await service.stop_recording("record-1", after_seq=0) == stopped
    await service.close(opened["sessionId"])
    factory.dispose()


@pytest.mark.asyncio
async def test_recording_pause_resume_preserves_confirmed_tail_and_is_idempotent(tmp_path):
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(profile()),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", tmp_path / "cloakbrowser", 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=Resources(),  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
        recordings=SqlAlchemyWorkflowRecordings(factory),
    )
    workers.service = service
    await service.open(profile_id="profile-1")
    await service.start_recording("record-pause")
    workers.recorded.append({"type": "input", "selector": "#name", "value": "暂停前"})

    paused = await service.pause_recording("record-pause", after_seq=0)
    assert paused["paused"] is True
    assert paused["data"]["events"][0]["value"] == "暂停前"
    assert service.recording_status("record-pause")["paused"] is True
    assert await service.pause_recording("record-pause", after_seq=1) == {
        "success": True, "sessionId": "record-pause", "recording": True,
        "paused": True, "nextSeq": 1, "hasMore": False, "data": {"events": []},
    }

    resumed = await service.resume_recording("record-pause", after_seq=1)
    assert resumed["paused"] is False
    assert service.recording_status("record-pause")["paused"] is False
    await service.resume_recording("record-pause", after_seq=1)
    assert [item["command"] for item in workers.commands].count("recorder_pause") == 1
    assert [item["command"] for item in workers.commands].count("recorder_resume") == 1
    await service.stop_recording("record-pause", after_seq=1)
    await service.close()
    factory.dispose()


@pytest.mark.asyncio
async def test_recording_limit_stops_capture_without_releasing_browser_early(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(workflow_recordings, "MAX_RECORDING_VALUE_BYTES", 4)
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", executable, 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=Resources(),  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
        recordings=SqlAlchemyWorkflowRecordings(factory),
    )
    workers.service = service
    opened = await service.open(profile_id="profile-1")
    await service.start_recording("record-limit")
    workers.recorded.append({"type": "input", "value": "超过上限"})

    with pytest.raises(WorkflowRunError) as limited:
        await service.recording_events("record-limit", after_seq=0)
    assert limited.value.code == "RECORDING_LIMIT_REACHED"
    assert [item["command"] for item in workers.commands][-1] == "recorder_stop"
    assert service.recording_status("record-limit")["recording"] is False
    assert (await service.status())["isOpen"] is True
    await service.close(opened["sessionId"])
    factory.dispose()


@pytest.mark.asyncio
async def test_recording_worker_exit_preserves_events_and_marks_interrupted(tmp_path):
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    resources = Resources()
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", executable, 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=resources,  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
        recordings=recordings,
    )
    workers.service = service
    opened = await service.open(profile_id="profile-1")
    await service.start_recording("record-crash")
    recordings.append(
        "record-crash",
        [{"type": "click", "selector": "#kept"}],
        now=datetime.now(UTC),
    )

    await service.on_worker_exit(opened["sessionId"], 7)

    with factory() as session:
        row = session.get(WorkflowRecordingSessionRow, "record-crash")
        assert row is not None
        assert row.status == "interrupted"
        assert row.active_slot is None
    assert recordings.events("record-crash", after_seq=0)["data"][0]["selector"] == "#kept"
    assert resources.owner_id is None
    factory.dispose()


@pytest.mark.asyncio
async def test_shutdown_stops_active_recording_before_browser_cleanup(tmp_path):
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    resources = Resources()
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", executable, 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=resources,  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
        recordings=recordings,
    )
    workers.service = service
    await service.open(profile_id="profile-1")
    await service.start_recording("record-shutdown")
    workers.recorded.append({"type": "click", "selector": "#tail"})

    await service.shutdown()

    assert recordings.status("record-shutdown")["recording"] is False
    assert recordings.events("record-shutdown", after_seq=0)["data"][0]["selector"] == "#tail"
    assert [command["command"] for command in workers.commands][-1] == "recorder_stop"
    assert resources.owner_id is None
    factory.dispose()


@pytest.mark.asyncio
async def test_recording_retries_drained_events_after_transient_database_failure(
    monkeypatch, tmp_path
):
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    recordings = SqlAlchemyWorkflowRecordings(factory)
    selected = profile()
    executable = tmp_path / "cloakbrowser"
    executable.write_text("")
    workers = Workers()
    service = WorkflowInspectionService(
        profiles=Profiles(selected),
        installed_kernels=lambda: [InstalledKernel("public", "146.0.1.1", executable, 1)],
        resolve_proxy=lambda _profile, _session: _none(),
        read_license=lambda: None,
        resources=Resources(),  # type: ignore[arg-type]
        workers=workers,  # type: ignore[arg-type]
        recordings=recordings,
    )
    workers.service = service
    await service.open(profile_id="profile-1")
    await service.start_recording("record-disk")
    workers.recorded.append({"type": "input", "selector": "#name", "value": "保留"})
    append = recordings.append
    attempts = 0

    def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("disk full")
        return append(*args, **kwargs)

    monkeypatch.setattr(recordings, "append", fail_once)

    with pytest.raises(WorkflowRunError) as failed:
        await service.recording_events("record-disk", after_seq=0)
    assert failed.value.code == "RECORDING_PERSIST_FAILED"
    assert service.recording_status("record-disk")["recording"] is True

    retried = await service.recording_events("record-disk", after_seq=0)
    assert retried["data"] == [
        {
            "sequence": 1,
            "type": "input",
            "selector": "#name",
            "value": "保留",
        }
    ]
    await service.stop_recording("record-disk", after_seq=1)
    await service.close()
    factory.dispose()


async def _none():
    return None
