import asyncio
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_environments import project_environments_router
from autoflow.application.environments.service import EnvironmentService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.environments.rules import environment_error
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
from autoflow.providers.browser.environment_browser import EnvironmentBrowserLauncher

PROFILE = "33333333-3333-3333-3333-333333333333"
PROFILE_KERNEL = "145.0.7632.109.2"


class _FakeContext:
    """Stand-in for a Playwright context, bound to the loop that opened it."""

    def __init__(self, loop=None) -> None:
        self.loop = loop
        self.closed = 0

    async def close(self) -> None:
        self.closed += 1
        if self.loop is not None:
            assert asyncio.get_running_loop() is self.loop


class _ProfileLookup:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def get(self, _profile_id: str) -> Profile:
        return self.profile


def _profile_record() -> Profile:
    now = datetime(2026, 9, 17, tzinfo=UTC)
    return Profile(
        PROFILE,
        ProfileSpec.from_values(
            {
                "name": "主账号",
                "start_url": "about:blank",
                "browser_version": PROFILE_KERNEL,
                "browser_edition": "public",
                "release_channel": "stable",
                "human_preset": "default",
            }
        ),
        31415,
        now,
        now,
    )


def test_end_waits_for_a_window_that_is_still_starting(tmp_path):
    """End during an in-flight open must still close the browser and save.

    The reported defect: the closer refused with INSTANCE_NOT_QUIESCENT while the
    window was still coming up, so "结束并保留" failed, nothing was saved and a live
    kernel stayed on the work copy. End must wait for that start, then close it
    and keep the login instead of answering with an error the user cannot clear.
    """

    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login-v1")
    service.environments.set_instance_state(instance.instance_id, "active")
    profile = _profile_record()
    kernel = InstalledKernel(
        "public", PROFILE_KERNEL, Path("/kernels/chromium/Chromium"), 1
    )
    gate = threading.Event()
    started = threading.Event()
    contexts: list[_FakeContext] = []

    async def launch(_directory: Path, _command: dict):
        started.set()
        while not gate.is_set():
            await asyncio.sleep(0.01)
        context = _FakeContext(asyncio.get_running_loop())
        contexts.append(context)
        return context

    launcher = EnvironmentBrowserLauncher(
        _ProfileLookup(profile), lambda: [kernel], service.store, launcher=launch
    )
    service._opener = launcher.opener
    service._closer = launcher.closer

    opened: list[object] = []
    open_thread = threading.Thread(
        daemon=True,
        target=lambda: opened.append(
            service.open_instance(
                project_id,
                instance.instance_id,
                str(uuid4()),
                {"expectedUseGeneration": 1},
            )
        )
    )
    open_thread.start()
    assert started.wait(10)

    ended: list[dict] = []
    end_thread = threading.Thread(
        target=lambda: ended.append(
            service.end(project_id, str(uuid4()), _end_body(instance))[0]
        ),
        daemon=True,
    )
    end_thread.start()
    try:
        time.sleep(0.3)
        assert ended == [], "End must wait for the start instead of failing the save"
    finally:
        gate.set()
    open_thread.join(30)
    end_thread.join(30)

    assert [context.closed for context in contexts] == [1]
    assert ended[0]["phase"] == "completed"
    assert ended[0]["saved"]["environmentId"]
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 1
    assert instance.instance_id not in service._opened
    assert (
        service.environments.get_instance(project_id, instance.instance_id).state
        == "cleaned"
    )


def test_end_handler_closes_browser_before_saving(tmp_path, monkeypatch):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"synthetic-login")
    service.environments.set_instance_state(instance.instance_id, "active")
    events = []

    def close_browser(_service, owned_instance):
        assert owned_instance.instance_id == instance.instance_id
        events.append("browser-closed")

    service._closer = close_browser
    stage = service.store.stage_candidate

    def stage_after_close(operation_id, instance_id):
        assert events == ["browser-closed"]
        events.append("snapshot")
        return stage(operation_id, instance_id)

    monkeypatch.setattr(service.store, "stage_candidate", stage_after_close)
    response = client.post(
        f"/api/v1/projects/{project_id}/tasks/{instance.active_task_id}/end",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "taskId": instance.active_task_id, "runId": instance.active_run_id,
            "instanceId": instance.instance_id, "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "retainEnvironment": {"enabled": True, "mode": "saveAs", "name": "关闭后保存"},
        },
    )
    assert response.status_code == 202
    assert response.json()["outcome"]["phase"] == "completed"
    assert events == ["browser-closed", "snapshot"]


def make(tmp_path, **kwargs):
    database = tmp_path / "environments.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    projects = ProjectService(SqlAlchemyProjects(factory))
    service = EnvironmentService(
        projects,
        SqlAlchemyEnvironments(factory),
        EnvironmentStore(tmp_path / "env-store"),
        **kwargs,
    )
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(project_environments_router(service))
    return TestClient(app), projects, service


def _project(projects):
    record, _operation, _replayed = projects.create(
        str(uuid4()), {"name": "环境项目", "description": ""}
    )
    return record.project_id


def _closed_instance(service, project_id, marker: bytes):
    resolved = service.resolve(project_id, {"source": "newFromProfile", "profileId": PROFILE})
    instance = service.reserve(
        project_id,
        resolved,
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    path = service.instance_path(instance.instance_id)
    (path / "Default").mkdir()
    (path / "Default" / "Cookies").write_bytes(marker)
    return service.environments.set_instance_state(instance.instance_id, "closed")


def test_list_get_patch_and_restore_saved_generation(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    empty = client.get(f"/api/v1/projects/{project_id}/environments")
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
    instance = _closed_instance(service, project_id, b"login-v1")
    key = str(uuid4())
    saved = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": key},
        json={
            "instanceId": instance.instance_id,
            "mode": "saveAs",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "name": "登录环境",
            "notes": "首次保存",
        },
    )
    assert saved.status_code == 202
    outcome = saved.json()["outcome"]
    assert outcome["phase"] == "completed"
    assert outcome["complete"] is True
    assert outcome["instance"]["state"] == "closed"
    environment_id = outcome["saved"]["environmentId"]
    assert outcome["saved"]["contentGeneration"] == 1
    replay = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": key},
        json={
            "instanceId": instance.instance_id,
            "mode": "saveAs",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "name": "登录环境",
            "notes": "首次保存",
        },
    )
    assert replay.status_code == 202
    assert replay.json()["operation"]["operationId"] == saved.json()["operation"]["operationId"]
    listed = client.get(f"/api/v1/projects/{project_id}/environments?q=登录")
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["name"] == "登录环境"
    detail = client.get(f"/api/v1/projects/{project_id}/environments/{environment_id}")
    assert detail.status_code == 200
    assert detail.json()["environment"]["ref"]["contentGeneration"] == 1
    patched = client.patch(
        f"/api/v1/projects/{project_id}/environments/{environment_id}",
        headers={"Idempotency-Key": str(uuid4())},
        json={"name": "主账号环境", "expectedMetadataRevision": 1},
    )
    assert patched.status_code == 200
    assert patched.json()["ref"]["metadataRevision"] == 2
    conflict = client.patch(
        f"/api/v1/projects/{project_id}/environments/{environment_id}",
        headers={"Idempotency-Key": str(uuid4())},
        json={"name": "冲突", "expectedMetadataRevision": 1},
    )
    assert conflict.status_code == 409
    restored = service.reserve(
        project_id,
        service.resolve(
            project_id, {"source": "fixedEnvironment", "environmentId": environment_id}
        ),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    cookies = service.instance_path(restored.instance_id) / "Default" / "Cookies"
    assert cookies.read_bytes() == b"login-v1"
    busy = service.resolve(
        project_id, {"source": "fixedEnvironment", "environmentId": environment_id}
    )
    try:
        service.reserve(
            project_id,
            busy,
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            holder_kind="maintenance",
            holder_id=str(uuid4()),
        )
    except ProjectError as error:
        assert getattr(error, "status", None) == 423
    else:
        raise AssertionError("expected exclusive occupancy")


def test_update_publishes_next_generation(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    first = _closed_instance(service, project_id, b"login-v1")
    created = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "instanceId": first.instance_id,
            "mode": "saveAs",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "name": "可更新环境",
        },
    ).json()["outcome"]["saved"]
    service.close_instance(project_id, first.instance_id, None)
    second = service.reserve(
        project_id,
        service.resolve(
            project_id,
            {"source": "fixedEnvironment", "environmentId": created["environmentId"]},
        ),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    (service.instance_path(second.instance_id) / "Default" / "Cookies").write_bytes(b"login-v2")
    service.environments.set_instance_state(second.instance_id, "closed")
    updated = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "instanceId": second.instance_id,
            "mode": "update",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "expectedContentGeneration": 1,
        },
    )
    assert updated.status_code == 202
    assert updated.json()["outcome"]["saved"]["contentGeneration"] == 2
    service.close_instance(project_id, second.instance_id, created["environmentId"])
    third = service.reserve(
        project_id,
        service.resolve(
            project_id,
            {"source": "fixedEnvironment", "environmentId": created["environmentId"]},
        ),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    assert (
        service.instance_path(third.instance_id) / "Default" / "Cookies"
    ).read_bytes() == b"login-v2"


def _account_record(service, project_id, table_name="账号"):
    from datetime import UTC, datetime

    from autoflow.application.project_data.tables import DataTableService
    from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
    from autoflow.infrastructure.database.project_data_models import DataRecordRow

    factory = service.environments._session_factory
    table, _, _ = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, str(uuid4()), {"name": table_name}
    )
    key = str(uuid4())
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(
            DataRecordRow(
                project_id=project_id,
                table_id=table["tableId"],
                dataset_generation=table["datasetGeneration"],
                key_type="uuid",
                key_value=key,
                values_json={},
                record_slots=[],
                status_id=None,
                current_environment_id=None,
                content_revision=1,
                status_revision=1,
                link_revision=1,
                deleted=False,
                created_at=now,
                updated_at=now,
            )
        )
    return {
        "recordRef": {
            "projectId": project_id,
            "tableId": table["tableId"],
            "datasetGeneration": table["datasetGeneration"],
            "recordKey": {"type": "uuid", "value": key},
        },
        "datasetGeneration": table["datasetGeneration"],
        "key": key,
    }


def test_save_links_record_and_repair_does_not_rerun(tmp_path):
    from autoflow.infrastructure.database.project_data_models import DataRecordRow

    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    account = _account_record(service, project_id)
    instance = _closed_instance(service, project_id, b"login-linked")
    saved = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "instanceId": instance.instance_id,
            "mode": "saveAs",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "name": "已关联环境",
            "recordTargets": [
                {
                    "recordRef": account["recordRef"],
                    "expectedLinkRevision": 1,
                    "replaceAllowed": False,
                }
            ],
        },
    )
    assert saved.status_code == 202
    assert saved.json()["outcome"]["phase"] == "completed"
    environment_id = saved.json()["outcome"]["saved"]["environmentId"]
    factory = service.environments._session_factory
    with factory() as session:
        row = session.get(
            DataRecordRow, (account["datasetGeneration"], "uuid", account["key"])
        )
        assert row.current_environment_id == environment_id
        assert row.link_revision == 2
    stale = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "instanceId": instance.instance_id,
            "mode": "saveAs",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "name": "冲突环境",
            "recordTargets": [
                {
                    "recordRef": account["recordRef"],
                    "expectedLinkRevision": 1,
                    "replaceAllowed": False,
                }
            ],
        },
    )
    assert stale.status_code == 202
    outcome = stale.json()["outcome"]
    assert outcome["phase"] == "saved_unlinked"
    assert outcome["complete"] is False
    assert outcome["saved"]["environmentId"] != environment_id
    repaired = client.post(
        f"/api/v1/projects/{project_id}/environment-operations/{stale.json()['operation']['operationId']}/repair",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "recordTargets": [
                {
                    "recordRef": account["recordRef"],
                    "expectedLinkRevision": 2,
                    "replaceAllowed": True,
                }
            ]
        },
    )
    assert repaired.status_code == 202
    assert repaired.json()["outcome"]["phase"] == "completed"
    with factory() as session:
        row = session.get(
            DataRecordRow, (account["datasetGeneration"], "uuid", account["key"])
        )
        assert row.current_environment_id == outcome["saved"]["environmentId"]
        assert row.link_revision == 3
    detail = client.get(f"/api/v1/projects/{project_id}/environments/{outcome['saved']['environmentId']}")
    assert detail.json()["linkedRecordCount"] == 1
    listed = client.get(f"/api/v1/projects/{project_id}/environments?q=冲突环境")
    assert listed.status_code == 200
    saved_row = next(
        item
        for item in listed.json()["items"]
        if item["ref"]["environmentId"] == outcome["saved"]["environmentId"]
    )
    # The directory artboard renders 最近来源 and 引用, so the list view carries them
    # instead of forcing one extra request per row.
    assert saved_row["createdFromSource"] == instance.source
    assert saved_row["createdFromTaskId"] == instance.active_task_id
    assert saved_row["linkedRecordCount"] == 1
    impact = client.get(
        f"/api/v1/projects/{project_id}/environments/{outcome['saved']['environmentId']}/impact?action=delete"
    )
    assert impact.status_code == 200
    linked_impact = impact.json()["impacts"][0]
    assert linked_impact["code"] == "ENVIRONMENT_RECORDS"
    assert linked_impact["resource"] == {
        "type": "environment",
        "projectId": project_id,
        "environmentId": outcome["saved"]["environmentId"],
    }


def test_binding_rechecks_revision_before_overwriting_concurrent_link(tmp_path):
    from copy import deepcopy

    import pytest

    from autoflow.domain.environments.rules import bind_targets
    from autoflow.domain.projects.models import ProjectError
    from autoflow.infrastructure.database.project_data_models import DataRecordRow

    _, projects, service = make(tmp_path)
    project_id = _project(projects)
    first = _account_record(service, project_id)
    second = {**first, "key": str(uuid4()), "recordRef": deepcopy(first["recordRef"])}
    second["recordRef"]["recordKey"]["value"] = second["key"]
    factory = service.environments._session_factory
    with factory.begin() as session:
        original = session.get(DataRecordRow, (first["datasetGeneration"], "uuid", first["key"]))
        values = {column.name: deepcopy(getattr(original, column.name)) for column in DataRecordRow.__table__.columns}
        values["key_value"] = second["key"]
        session.add(DataRecordRow(**values))
    target = str(uuid4())
    requested = [{"recordRef": record["recordRef"], "expectedLinkRevision": 1,
                  "replaceAllowed": True} for record in (first, second)]
    results = bind_targets(target, service.environments.load_bind_targets(project_id, requested))
    factory = service.environments._session_factory
    concurrent_environment = str(uuid4())
    with factory() as session:
        row = session.get(DataRecordRow, (second["datasetGeneration"], "uuid", second["key"]))
        row.current_environment_id = concurrent_environment
        row.link_revision = 2
        session.commit()
    with pytest.raises(ProjectError) as conflict:
        service.environments.bind_records(project_id, target, results)
    assert conflict.value.code == "LINK_REVISION_CONFLICT"
    with factory() as session:
        row = session.get(DataRecordRow, (first["datasetGeneration"], "uuid", first["key"]))
        assert row.current_environment_id is None and row.link_revision == 1
        row = session.get(DataRecordRow, (second["datasetGeneration"], "uuid", second["key"]))
        assert row.current_environment_id == concurrent_environment and row.link_revision == 2


def test_open_records_the_failure_instead_of_leaving_it_running(tmp_path):
    """An accepted operation that can only answer "still running" is a dead end."""

    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login-v1")
    service.environments.set_instance_state(instance.instance_id, "active")

    def refuse(_service, _instance):
        raise environment_error(
            "INSTANCE_NOT_QUIESCENT", "工作副本正被任务内的浏览器占用", 409
        )

    service._opener = refuse
    key = str(uuid4())
    response = client.post(
        f"/api/v1/projects/{project_id}/environment-instances/{instance.instance_id}/open",
        headers={"Idempotency-Key": key},
        json={"expectedUseGeneration": 1},
    )

    assert response.status_code == 409
    recorded = service.environments.operation_by_key(key)
    assert recorded.status == "failed"
    assert recorded.error["code"] == "INSTANCE_NOT_QUIESCENT"
    assert instance.instance_id not in service._opened


def test_open_records_an_unexpected_launch_failure_instead_of_leaving_it_running(tmp_path):
    """A launch failure the domain does not name must still close the request.

    The reported defect: ``openInstance`` stayed ``running`` forever whenever the
    launcher raised something other than ``ProjectError`` (a Chromium
    ``ProcessSingleton`` error, an OS error, a timeout), so the user could only
    ever poll a request that would never finish.
    """

    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login-v1")
    service.environments.set_instance_state(instance.instance_id, "active")

    def explode(_service, _instance):
        raise RuntimeError("ProcessSingleton: the profile is already in use")

    service._opener = explode
    key = str(uuid4())
    with pytest.raises(RuntimeError):
        client.post(
            f"/api/v1/projects/{project_id}/environment-instances/{instance.instance_id}/open",
            headers={"Idempotency-Key": key},
            json={"expectedUseGeneration": 1},
        )

    recorded = service.environments.operation_by_key(key)
    assert recorded.status == "failed"
    assert recorded.error["code"] == "INSTANCE_OPEN_FAILED"
    assert instance.instance_id not in service._opened


def test_live_capacity_and_open_instance(tmp_path):
    client, projects, _service = make(tmp_path)
    limited = EnvironmentService(
        projects,
        _service.environments,
        _service.store,
        max_live_instances=1,
    )
    project_id = _project(projects)
    first = limited.reserve(
        project_id,
        limited.resolve(project_id, {"source": "newFromProfile", "profileId": PROFILE}),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    try:
        limited.reserve(
            project_id,
            limited.resolve(project_id, {"source": "newFromProfile", "profileId": PROFILE}),
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            holder_kind="task",
            holder_id=str(uuid4()),
        )
    except ProjectError as error:
        assert getattr(error, "code", None) == "CAPACITY_EXHAUSTED"
        assert getattr(error, "status", None) == 429
    else:
        raise AssertionError("expected live capacity to be exhausted")
    missing_key = str(uuid4())
    missing = client.post(
        f"/api/v1/projects/{project_id}/environment-instances/{first.instance_id}/open",
        headers={"Idempotency-Key": missing_key},
        json={"expectedUseGeneration": 1},
    )
    assert missing.status_code == 503
    assert first.instance_id not in _service._opened
    assert _service.environments.operation_by_key(missing_key) is None
    launches = []
    _service._opener = lambda _owner, instance: launches.append(instance.instance_id)
    opened = client.post(
        f"/api/v1/projects/{project_id}/environment-instances/{first.instance_id}/open",
        headers={"Idempotency-Key": str(uuid4())},
        json={"expectedUseGeneration": 1},
    )
    assert opened.status_code == 202
    assert opened.json()["outcome"]["phase"] == "open"
    assert opened.json()["outcome"]["instance"]["state"] == "active"
    replay = client.post(
        f"/api/v1/projects/{project_id}/environment-instances/{first.instance_id}/open",
        headers={"Idempotency-Key": opened.json()["operation"]["idempotencyKey"]},
        json={"expectedUseGeneration": 1},
    )
    assert replay.json()["operation"]["operationId"] == opened.json()["operation"]["operationId"]
    assert launches == [first.instance_id]


def test_manual_list_searches_reason_and_task_and_orders_by_retention(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    late_instance = _closed_instance(service, project_id, b"manual-late")
    soon_instance = _closed_instance(service, project_id, b"manual-soon")
    late = service.open_manual(
        project_id,
        {
            "taskId": str(uuid4()),
            "runId": str(uuid4()),
            "instanceId": late_instance.instance_id,
            "reason": "需要核对提取的标题与日期",
            "expiresAt": datetime(2026, 9, 18, 13, 43, tzinfo=UTC),
        },
    )
    soon = service.open_manual(
        project_id,
        {
            "taskId": str(uuid4()),
            "runId": str(uuid4()),
            "instanceId": soon_instance.instance_id,
            "reason": "需要输入短信验证码",
            "expiresAt": datetime(2026, 9, 18, 13, 12, tzinfo=UTC),
        },
    )
    sorted_items = client.get(
        f"/api/v1/projects/{project_id}/manual-items", params={"sort": "expiresAt"}
    )
    assert [
        item["manualItemId"] for item in sorted_items.json()["items"]
    ] == [soon["manualItemId"], late["manualItemId"]]
    by_reason = client.get(
        f"/api/v1/projects/{project_id}/manual-items", params={"q": "验证码"}
    )
    assert by_reason.json()["total"] == 1
    assert by_reason.json()["items"][0]["manualItemId"] == soon["manualItemId"]
    by_task = client.get(
        f"/api/v1/projects/{project_id}/manual-items", params={"q": late["taskId"][:8]}
    )
    assert [item["manualItemId"] for item in by_task.json()["items"]] == [
        late["manualItemId"]
    ]
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/manual-items", params={"sort": "bogus"}
        ).status_code
        == 422
    )


def test_manual_resume_timeout_and_repeat_have_one_winner(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"manual")
    item = service.open_manual(
        project_id,
        {
            "taskId": str(uuid4()),
            "runId": str(uuid4()),
            "instanceId": instance.instance_id,
            "reason": "需要验证码",
        },
    )
    first = client.post(
        f"/api/v1/projects/{project_id}/manual-items/{item['manualItemId']}/resume",
        headers={"Idempotency-Key": str(uuid4())},
        json={"checkpointRevision": 1, "expectedStatusRevision": 1},
    )
    assert first.status_code == 202
    assert first.json()["outcome"]["item"]["status"] == "resume_requested"
    listed = client.get(f"/api/v1/projects/{project_id}/manual-items")
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["statusRevision"] == 2
    second = client.post(
        f"/api/v1/projects/{project_id}/manual-items/{item['manualItemId']}/resume",
        headers={"Idempotency-Key": str(uuid4())},
        json={"checkpointRevision": 1, "expectedStatusRevision": 1},
    )
    assert second.status_code == 409
    started = service.begin_resume(project_id, item["manualItemId"], 2)
    assert started["status"] == "resolved"
    assert started["resumeStarted"] is True
    try:
        service.expire_manual(project_id, item["manualItemId"], started["statusRevision"])
    except ProjectError as error:
        assert getattr(error, "code", None) == "MANUAL_ALREADY_RESOLVED"
    else:
        raise AssertionError("timeout cannot replace a started resume")


def _stored_digest(service, environment_id: str) -> str:
    from autoflow.infrastructure.database.environment_models import (
        ProjectEnvironmentRow,
    )

    with service.environments._session_factory() as session:
        return session.get(ProjectEnvironmentRow, environment_id).current_digest


def _end_body(instance, *, name="登录环境"):
    return {
        "taskId": instance.active_task_id,
        "runId": instance.active_run_id,
        "instanceId": instance.instance_id,
        "expectedUseGeneration": 1,
        "executionGeneration": 1,
        "retainEnvironment": {"enabled": True, "mode": "saveAs", "name": name},
    }


def test_production_environment_operations_are_readable_in_project_ledger(tmp_path):
    from autoflow.adapters.http.projects import projects_router
    from autoflow.application.projects.overview import ProjectOverviewService

    client, projects, service = make(tmp_path)
    client.app.include_router(projects_router(
        projects, ProjectOverviewService(service.environments._session_factory)
    ))
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"ledger")
    key = str(uuid4())
    response = client.post(
        f"/api/v1/projects/{project_id}/tasks/{instance.active_task_id}/end",
        headers={"Idempotency-Key": key}, json=_end_body(instance),
    )
    assert response.status_code == 202, response.text
    operation = response.json()['operation']
    for suffix in ('', f"/{operation['operationId']}", f'/by-idempotency-key/{key}'):
        result = client.get(f'/api/v1/projects/{project_id}/operations{suffix}')
        assert result.status_code == 200, result.text
        if suffix:
            assert result.json() == operation
        else:
            saved = [item for item in result.json()['items'] if item['kind'] == 'saveEnvironment']
            assert len(saved) == 2  # End and its durable save operation.
            assert operation in saved


def test_end_retry_after_lost_response_resumes_without_second_environment(
    tmp_path, monkeypatch
):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login-v1")
    service.environments.set_instance_state(instance.instance_id, "active")
    service._closer = lambda *_: None
    key = str(uuid4())
    url = f"/api/v1/projects/{project_id}/tasks/{instance.active_task_id}/end"
    body = _end_body(instance)

    stage = service.store.stage_candidate
    attempts = {"count": 0}

    def flaky_stage(operation_id, instance_id):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("simulated process loss before publish")
        return stage(operation_id, instance_id)

    monkeypatch.setattr(service.store, "stage_candidate", flaky_stage)
    with pytest.raises(RuntimeError):
        client.post(url, headers={"Idempotency-Key": key}, json=body)
    listed = client.get(f"/api/v1/projects/{project_id}/environments").json()
    assert listed["total"] == 0

    retry = client.post(url, headers={"Idempotency-Key": key}, json=body)
    assert retry.status_code == 202
    outcome = retry.json()["outcome"]
    assert outcome["phase"] == "completed"
    assert outcome["saved"]["environmentId"]
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 1

    again = client.post(url, headers={"Idempotency-Key": key}, json=body)
    assert again.status_code == 202
    assert (
        again.json()["outcome"]["saved"]["environmentId"]
        == outcome["saved"]["environmentId"]
    )
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 1


def test_end_retry_after_completion_loss_keeps_one_environment(tmp_path, monkeypatch):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login-v1")
    service.environments.set_instance_state(instance.instance_id, "active")
    service._closer = lambda *_: None
    key = str(uuid4())
    url = f"/api/v1/projects/{project_id}/tasks/{instance.active_task_id}/end"
    body = _end_body(instance)

    complete = service.environments.complete_operation
    calls = {"count": 0}

    def flaky_complete(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("simulated loss after the environment was published")
        return complete(*args, **kwargs)

    monkeypatch.setattr(service.environments, "complete_operation", flaky_complete)
    with pytest.raises(RuntimeError):
        client.post(url, headers={"Idempotency-Key": key}, json=body)
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 1

    retry = client.post(url, headers={"Idempotency-Key": key}, json=body)
    assert retry.status_code == 202
    assert retry.json()["outcome"]["phase"] == "completed"
    assert retry.json()["outcome"]["saved"]["environmentId"]
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 1


def test_save_retry_after_lost_response_republishes_same_environment(
    tmp_path, monkeypatch
):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login-v1")
    key = str(uuid4())
    url = f"/api/v1/projects/{project_id}/environment-saves"
    body = {
        "instanceId": instance.instance_id,
        "mode": "saveAs",
        "expectedUseGeneration": 1,
        "executionGeneration": 1,
        "name": "登录环境",
    }

    complete = service.environments.complete_operation
    calls = {"count": 0}

    def flaky_complete(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated loss after publish")
        return complete(*args, **kwargs)

    monkeypatch.setattr(service.environments, "complete_operation", flaky_complete)
    with pytest.raises(RuntimeError):
        client.post(url, headers={"Idempotency-Key": key}, json=body)

    retry = client.post(url, headers={"Idempotency-Key": key}, json=body)
    assert retry.status_code == 202
    assert retry.json()["outcome"]["saved"]["environmentId"]
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 1

    again = client.post(url, headers={"Idempotency-Key": key}, json=body)
    assert again.status_code == 202
    assert (
        again.json()["outcome"]["saved"]["environmentId"]
        == retry.json()["outcome"]["saved"]["environmentId"]
    )
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 1


def test_save_uses_the_run_execution_generation_instead_of_the_request(tmp_path):
    class _Run:
        execution_generation = 4

    client, projects, service = make(
        tmp_path, execution_generation_lookup=lambda _run_id: _Run()
    )
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login-v1")
    url = f"/api/v1/projects/{project_id}/environment-saves"
    body = {
        "instanceId": instance.instance_id,
        "mode": "saveAs",
        "expectedUseGeneration": 1,
        "name": "登录环境",
    }

    stale = client.post(
        url, headers={"Idempotency-Key": str(uuid4())},
        json={**body, "executionGeneration": 3, "currentExecutionGeneration": 3},
    )
    assert stale.status_code == 410
    assert stale.json()["error"]["code"] == "EXECUTION_GENERATION_REVOKED"
    assert client.get(f"/api/v1/projects/{project_id}/environments").json()["total"] == 0

    current = client.post(
        url, headers={"Idempotency-Key": str(uuid4())},
        json={**body, "executionGeneration": 4},
    )
    assert current.status_code == 202
    assert current.json()["outcome"]["phase"] == "completed"

def test_late_update_cannot_overwrite_a_newer_published_generation(tmp_path):
    """A save that read the old source must not replace newer published content."""

    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    first = _closed_instance(service, project_id, b"login-v1")
    created = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "instanceId": first.instance_id,
            "mode": "saveAs",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "name": "迟到保存环境",
        },
    ).json()["outcome"]["saved"]
    environment_id = created["environmentId"]
    service.close_instance(project_id, first.instance_id, None)
    second = service.reserve(
        project_id,
        service.resolve(
            project_id, {"source": "fixedEnvironment", "environmentId": environment_id}
        ),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    (service.instance_path(second.instance_id) / "Default" / "Cookies").write_bytes(b"v2")
    service.environments.set_instance_state(second.instance_id, "closed")
    published = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "instanceId": second.instance_id,
            "mode": "update",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "expectedContentGeneration": 1,
        },
    ).json()["outcome"]["saved"]
    assert published["contentGeneration"] == 2
    service.close_instance(project_id, second.instance_id, environment_id)
    newer_digest = _stored_digest(service, environment_id)

    # The request-level guard already stops a stale expected generation.
    third = service.reserve(
        project_id,
        service.resolve(
            project_id, {"source": "fixedEnvironment", "environmentId": environment_id}
        ),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    (service.instance_path(third.instance_id) / "Default" / "Cookies").write_bytes(b"v3")
    service.environments.set_instance_state(third.instance_id, "closed")
    stale = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "instanceId": third.instance_id,
            "mode": "update",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "expectedContentGeneration": 1,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "SAVE_GENERATION_CONFLICT"

    # The publish step refuses the stale generation even if a caller skips that
    # guard, which is the window a slow save used to sail through.
    with pytest.raises(ProjectError) as raced:
        service.environments.publish_update(
            project_id, environment_id, "stale-digest", generation=2
        )
    assert raced.value.code == "SAVE_GENERATION_CONFLICT"
    service.close_instance(project_id, third.instance_id, environment_id)
    current = service.environments.get(project_id, environment_id)
    assert current.ref.content_generation == 2
    assert _stored_digest(service, environment_id) == newer_digest

def test_end_links_only_the_selected_records(tmp_path):
    """The shared person row stays untouched when only the account is selected."""

    from autoflow.infrastructure.database.project_data_models import DataRecordRow

    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    account = _account_record(service, project_id)
    shared_person = _account_record(service, project_id, table_name="人员")
    instance = _closed_instance(service, project_id, b"email-and-account")
    response = client.post(
        f"/api/v1/projects/{project_id}/tasks/{instance.active_task_id}/end",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "taskId": instance.active_task_id,
            "runId": instance.active_run_id,
            "instanceId": instance.instance_id,
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "retainEnvironment": {
                "enabled": True,
                "mode": "saveAs",
                "name": "邮箱与账号环境",
                "recordTargets": [
                    {
                        "recordRef": account["recordRef"],
                        "expectedLinkRevision": 1,
                        "replaceAllowed": False,
                    }
                ],
            },
        },
    )
    assert response.status_code == 202
    outcome = response.json()["outcome"]
    assert outcome["phase"] == "completed"
    assert [item["recordKey"] for item in outcome["targets"]] == [
        account["recordRef"]["recordKey"]
    ]
    factory = service.environments._session_factory
    with factory() as session:
        linked = session.get(
            DataRecordRow, (account["datasetGeneration"], "uuid", account["key"])
        )
        untouched = session.get(
            DataRecordRow,
            (shared_person["datasetGeneration"], "uuid", shared_person["key"]),
        )
        assert linked.current_environment_id == outcome["saved"]["environmentId"]
        assert linked.link_revision == 2
        assert untouched.current_environment_id is None
        assert untouched.link_revision == 1


def test_io_failure_after_publication_keeps_ownership_until_original_key_recovers(tmp_path, monkeypatch):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    initial = _closed_instance(service, project_id, b"login-v1")
    prefix = f"/api/v1/projects/{project_id}"
    saved = client.post(prefix + f"/tasks/{initial.active_task_id}/end", headers={"Idempotency-Key": str(uuid4())}, json=_end_body(initial)).json()["outcome"]["saved"]
    environment_id = saved["environmentId"]
    source = service.resolve(project_id, {"source": "fixedEnvironment", "environmentId": environment_id})
    instance = service.reserve(project_id, source, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind="task", holder_id=str(uuid4()))
    service.environments.set_instance_state(instance.instance_id, "closed")
    previous_key = str(uuid4())
    previous_body = {"instanceId": instance.instance_id, "mode": "update", "expectedUseGeneration": 1, "executionGeneration": 1, "expectedContentGeneration": 1}
    previous = client.post(prefix + '/environment-saves', headers={'Idempotency-Key': previous_key}, json=previous_body)
    assert previous.status_code == 202, previous.text
    publish = service.store.publish

    def publish_then_lose_ack(*args):
        publish(*args)
        raise OSError("injected failure after generation publication")

    monkeypatch.setattr(service.store, "publish", publish_then_lose_ack)
    key = str(uuid4())
    body = {**previous_body, "expectedContentGeneration": 2}
    with pytest.raises(OSError):
        client.post(prefix + "/environment-saves", headers={"Idempotency-Key": key}, json=body)
    assert service.environments.get_instance(project_id, instance.instance_id).state == "saving"
    assert service.store.generation_dir(environment_id, 3).is_dir()
    # Replaying an earlier successful command cannot release a later unknown save.
    replay = client.post(prefix + '/environment-saves', headers={'Idempotency-Key': previous_key}, json=previous_body)
    assert replay.status_code == 202
    assert replay.json()['outcome'] == previous.json()['outcome']
    with pytest.raises(ProjectError) as busy:
        service.reserve(project_id, source, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind="task", holder_id=str(uuid4()))
    assert busy.value.code == "ENVIRONMENT_BUSY"
    monkeypatch.setattr(service.store, "publish", publish)
    recovered = client.post(prefix + "/environment-saves", headers={"Idempotency-Key": key}, json=body)
    assert recovered.status_code == 202, recovered.text
    assert recovered.json()["outcome"]["saved"]["contentGeneration"] == 3
    repeated = client.post(prefix + "/environment-saves", headers={"Idempotency-Key": key}, json=body).json()
    assert repeated['outcome'] == recovered.json()['outcome']
    assert repeated['operation']['operationId'] == recovered.json()['operation']['operationId']
    assert not service.store.generation_dir(environment_id, 4).exists()


def test_retained_update_reacquires_source_without_displacing_live_owner(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    prefix = f"/api/v1/projects/{project_id}"
    initial = _closed_instance(service, project_id, b"login-v1")
    saved = client.post(prefix + f"/tasks/{initial.active_task_id}/end", headers={"Idempotency-Key": str(uuid4())}, json=_end_body(initial)).json()["outcome"]["saved"]
    environment_id = saved['environmentId']
    source = service.resolve(project_id, {'source': 'fixedEnvironment', 'environmentId': environment_id})
    t1 = service.reserve(project_id, source, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind='task', holder_id=str(uuid4()))
    service.environments.set_instance_state(t1.instance_id, 'retained_unsaved')
    assert service.environments.count_live_instances(project_id) == 0
    t2 = service.reserve(project_id, source, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind='task', holder_id=str(uuid4()))
    body = {'instanceId': t1.instance_id, 'mode': 'update', 'expectedUseGeneration': 1, 'executionGeneration': 1, 'expectedContentGeneration': 1}
    blocked = client.post(prefix + '/environment-saves', headers={'Idempotency-Key': str(uuid4())}, json=body)
    assert blocked.status_code == 423, blocked.text
    assert blocked.json()['error']['code'] == 'ENVIRONMENT_BUSY'
    current, owner = service.environments.get_with_instance(project_id, environment_id)
    assert owner.instance_id == t2.instance_id
    assert current.ref.content_generation == 1
    assert not service.store.generation_dir(environment_id, 2).exists()
    service.environments.set_instance_state(t2.instance_id, 'closed')
    service.close_instance(project_id, t2.instance_id, environment_id)
    retry = client.post(prefix + '/environment-saves', headers={'Idempotency-Key': str(uuid4())}, json=body)
    assert retry.status_code == 202, retry.text
    assert retry.json()['outcome']['saved']['contentGeneration'] == 2
    _, owner = service.environments.get_with_instance(project_id, environment_id)
    assert owner is None
    next_source = service.resolve(project_id, {'source': 'fixedEnvironment', 'environmentId': environment_id})
    service.reserve(project_id, next_source, task_id=str(uuid4()), run_id=str(uuid4()), holder_kind='task', holder_id=str(uuid4()))


def test_manual_deadline_round_trips_utc_in_detail_and_list(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b'manual-timezone')
    deadline = datetime(2026, 9, 21, 7, 15, tzinfo=UTC)
    item = service.open_manual(project_id, {'taskId': str(uuid4()), 'runId': str(uuid4()), 'instanceId': instance.instance_id, 'expiresAt': deadline})
    base = f"/api/v1/projects/{project_id}/manual-items"
    detail = client.get(base + '/' + item['manualItemId']).json()
    listed = client.get(base).json()['items'][0]
    for result in [detail, listed]:
        assert datetime.fromisoformat(result['expiresAt']) == deadline
        assert datetime.fromisoformat(result['createdAt']).tzinfo is not None
