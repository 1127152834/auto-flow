from __future__ import annotations

from datetime import UTC, datetime

import pytest
from autoflow.application.workflows.inspection import WorkflowInspectionService
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.workflows.browser import WorkflowBrowserBusy
from autoflow.domain.workflows.runs import WorkflowRunError


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
        }.get(action, {"success": True})
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


async def _none():
    return None
