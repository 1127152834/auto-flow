"""Real SQLite project ownership/lifecycle with controlled inspection worker protocol.

These tests verify admission and durable facts, not real-browser capture behavior.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import select

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflow_inspection import workflow_inspection_router
from autoflow.application.projects.lifecycle import (
    ProjectLifecycleCoordinator,
    ProjectLifecycleService,
)
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.inspection import WorkflowInspectionService
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database import session as database_session
from autoflow.infrastructure.database.project_lifecycle import (
    SqlAlchemyProjectLifecycle,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_models import (
    WorkflowDocumentRow,
    WorkflowRecordingCommandRow,
    WorkflowRecordingReviewRow,
    WorkflowRecordingSessionRow,
)
from autoflow.infrastructure.database.workflow_recordings import (
    SqlAlchemyWorkflowRecordings,
)
from tests.integration.test_project_lifecycle import Context, key
from tests.unit.workflows.test_inspection_service import (
    Profiles,
    Resources,
    Workers,
    profile,
)


class ControlledWorkers(Workers):
    def __init__(self):
        super().__init__()
        self.start_count = 0
        self.start_entered = asyncio.Event()
        self.allow_start = asyncio.Event()
        self.allow_start.set()
        self.fail_stop = False
        self.fail_start = False

    async def start(self, session_id, profile_id, executable, payload):
        self.start_count += 1
        await super().start(session_id, profile_id, executable, payload)
        self.start_entered.set()
        await self.allow_start.wait()
        if self.fail_start:
            raise RuntimeError("controlled startup failure")

    async def stop(self, session_id):
        if self.fail_stop:
            raise RuntimeError("controlled cleanup failure")
        await super().stop(session_id)


@pytest.fixture
def scoped_inspection(tmp_path):
    ctx = Context(tmp_path)
    other, _, _ = ctx.projects.create(key(), {"name": "另一个项目", "description": ""})
    recordings = SqlAlchemyWorkflowRecordings(ctx.factory)
    workers, resources = ControlledWorkers(), Resources()
    executable = tmp_path / "protocol-only-cloakbrowser"
    executable.write_text("fixture: never executed")

    async def no_proxy(_profile, _session):
        return None

    inspection = WorkflowInspectionService(
        profiles=Profiles(profile()),
        installed_kernels=lambda: [
            InstalledKernel("public", "146.0.1.1", executable, 1)
        ],
        resolve_proxy=no_proxy,
        read_license=lambda: None,
        workers=workers,
        resources=resources,
        recordings=recordings,
    )
    workers.service = inspection
    ctx.repository = SqlAlchemyProjectLifecycle(
        ctx.factory, inspection_blockers=inspection.project_blockers
    )
    ctx.coordinator = ProjectLifecycleCoordinator(ctx.repository, QuiesceGate())
    ctx.service = ProjectLifecycleService(
        SqlAlchemyProjects(ctx.factory), ctx.repository, ctx.coordinator
    )
    yield ctx, other.project_id, inspection, recordings, workers, resources
    ctx.factory.dispose()


@pytest.mark.asyncio
async def test_same_profile_does_not_allow_cross_project_browser_reuse(
    scoped_inspection,
):
    ctx, other, inspection, _, workers, resources = scoped_inspection
    own = ctx.project_id
    opened = await inspection.open(profile_id="profile-1", project_id=own)
    assert await inspection.open(profile_id="profile-1", project_id=own) == opened
    assert workers.start_count == 1
    for foreign in (other, None):
        with pytest.raises(WorkflowRunError) as refused:
            await inspection.open(profile_id="profile-1", project_id=foreign)
        assert refused.value.status == 404
        with pytest.raises(WorkflowRunError):
            inspection.check_project_access(foreign)
        with pytest.raises(WorkflowRunError):
            await inspection.close(opened["sessionId"], project_id=foreign)
        assert workers.busy()
    assert inspection.project_blockers(other) == []
    assert len(inspection.project_blockers(own)) == 1
    blocker = inspection.project_blockers(own)[0]
    assert blocker["resource"] == {"type": "project", "projectId": own}
    assert blocker["state"] == "ready"
    assert resources.owner_id == opened["sessionId"]
    await inspection.close(opened["sessionId"], project_id=ctx.project_id)
    assert inspection.project_blockers(own) == []


@pytest.mark.asyncio
async def test_starting_claim_blocks_archive_before_worker_start_returns(
    scoped_inspection,
):
    ctx, _, inspection, _, workers, _ = scoped_inspection
    workers.allow_start.clear()
    opening = asyncio.create_task(
        inspection.open(profile_id="profile-1", project_id=ctx.project_id)
    )
    try:
        await asyncio.wait_for(workers.start_entered.wait(), 2)
        assert not opening.done()
        impact = ctx.service.impact(ctx.project_id, "archive")
        assert any(
            row["code"] == "STUDIO_INSPECTION_ACTIVE" for row in impact["blockers"]
        )
        ctx.archive()
        ctx.repository.advance(ctx.project_id)
        assert ctx.state() == "closing"
        workers.allow_start.set()
        opened = await asyncio.wait_for(opening, 2)
        ctx.repository.advance(ctx.project_id)
        assert ctx.state() == "closing"
        await inspection.close(opened["sessionId"], project_id=ctx.project_id)
        ctx.repository.advance(ctx.project_id)
        assert ctx.state() == "archived"
    finally:
        workers.allow_start.set()
        if not opening.done():
            await opening


@pytest.mark.asyncio
@pytest.mark.parametrize("settle", [False, True])
async def test_archive_wins_admission_without_starting_worker(
    scoped_inspection, settle
):
    ctx, _, inspection, _, workers, resources = scoped_inspection
    ctx.archive()
    if settle:
        ctx.repository.advance(ctx.project_id)
    with pytest.raises(ProjectError) as refused:
        await inspection.open(profile_id="profile-1", project_id=ctx.project_id)
    assert refused.value.status in (409, 423)
    assert workers.start_count == 0
    assert (
        resources.owner_id is None and inspection.project_blockers(ctx.project_id) == []
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("during_start", [False, True])
async def test_cleanup_failure_preserves_claim_until_retry(
    scoped_inspection, during_start
):
    ctx, _, inspection, _, workers, resources = scoped_inspection
    if during_start:
        workers.fail_start = workers.fail_stop = True
        with pytest.raises(RuntimeError, match="cleanup failure"):
            await inspection.open(profile_id="profile-1", project_id=ctx.project_id)
        opened = await inspection.status()
    else:
        opened = await inspection.open(
            profile_id="profile-1", project_id=ctx.project_id
        )
        workers.fail_stop = True
        with pytest.raises(RuntimeError, match="cleanup failure"):
            await inspection.close(opened["sessionId"], project_id=ctx.project_id)
    assert opened["isOpen"] and workers.busy()
    assert resources.owner_id == opened["sessionId"]
    assert inspection.project_blockers(ctx.project_id)
    ctx.archive()
    ctx.repository.advance(ctx.project_id)
    assert ctx.state() == "closing"
    workers.fail_stop = False
    await inspection.close(opened["sessionId"], project_id=ctx.project_id)
    assert not workers.busy() and resources.owner_id is None
    assert inspection.project_blockers(ctx.project_id) == []
    ctx.repository.advance(ctx.project_id)
    assert ctx.state() == "archived"


@pytest.mark.asyncio
async def test_closing_blocks_new_capture_but_allows_recording_tail_and_browser_cleanup(
    scoped_inspection,
):
    ctx, _, inspection, recordings, workers, _ = scoped_inspection
    own = ctx.project_id
    opened = await inspection.open(profile_id="profile-1", project_id=own)
    await inspection.recording_command(
        "start",
        action="start",
        session_id="record",
        project_id=own,
        document_id="unsaved",
    )
    workers.recorded.append(
        {"type": "input", "selector": "#field", "value": "归档前尾部"}
    )
    ctx.archive()
    ctx.repository.advance(own)
    assert ctx.state() == "closing"
    before = list(workers.commands)
    for action in ("start", "resume"):
        with pytest.raises(ProjectError):
            await inspection.recording_command(
                f"closing-{action}", action=action, session_id="record", project_id=own
            )
    assert workers.commands == before
    stopped = await inspection.recording_command(
        "stop", action="stop", session_id="record", project_id=own
    )
    assert stopped["data"]["events"][0]["value"] == "归档前尾部"
    assert recordings.events("record", after_seq=0, project_id=own)["nextSeq"] == 1
    ctx.repository.advance(own)
    assert ctx.state() == "closing", (
        "Stopping recording alone must retain the visible browser claim"
    )
    await inspection.close(opened["sessionId"], project_id=ctx.project_id)
    ctx.repository.advance(own)
    assert ctx.state() == "archived"
    assert (
        inspection.recording_command_status("stop", project_id=own)["status"]
        == "completed"
    )


@pytest.mark.asyncio
async def test_recording_session_receipts_and_events_are_owned_and_durable(
    scoped_inspection,
):
    ctx, other, inspection, recordings, workers, _ = scoped_inspection
    own = ctx.project_id
    opened = await inspection.open(profile_id="profile-1", project_id=own)
    kwargs = {
        "action": "start",
        "session_id": "record-a",
        "project_id": own,
        "document_id": "unsaved-a",
    }
    first = await inspection.recording_command("start-a", **kwargs)
    assert await inspection.recording_command("start-a", **kwargs) == first
    assert sum(row["command"] == "recorder_start" for row in workers.commands) == 1
    workers.recorded.append({"type": "click", "selector": "#project-a"})
    assert (await inspection.recording_events("record-a", after_seq=0, project_id=own))[
        "data"
    ][0]["selector"] == "#project-a"
    for foreign in (other, None):
        for read in (
            lambda foreign=foreign: recordings.status("record-a", project_id=foreign),
            lambda foreign=foreign: recordings.events(
                "record-a", after_seq=0, project_id=foreign
            ),
            lambda foreign=foreign: inspection.recording_command_status(
                "start-a", project_id=foreign
            ),
        ):
            with pytest.raises(WorkflowRunError) as refused:
                read()
            assert refused.value.status == 404
        with pytest.raises(WorkflowRunError):
            await inspection.recording_command(
                "start-a", action="start", session_id="record-a", project_id=foreign
            )
        assert recordings.current(project_id=foreign) is None
    await inspection.recording_command(
        "stop-a", action="stop", session_id="record-a", project_id=own
    )
    await inspection.close(opened["sessionId"], project_id=ctx.project_id)
    rebuilt = SqlAlchemyWorkflowRecordings(ctx.factory)
    assert (
        rebuilt.events("record-a", after_seq=0, project_id=own)["data"][0]["selector"]
        == "#project-a"
    )
    assert rebuilt.command("start-a", project_id=own)["status"] == "completed"
    with ctx.factory() as session:
        row = session.get(WorkflowRecordingSessionRow, "record-a")
        assert row.project_id == own and row.document_id == "unsaved-a"
        assert session.get(WorkflowRecordingCommandRow, "start-a").project_id == own


@pytest.mark.asyncio
async def test_repeated_start_cannot_rebind_active_recording_document(
    scoped_inspection,
):
    ctx, _, inspection, _, workers, _ = scoped_inspection
    opened = await inspection.open(profile_id="profile-1", project_id=ctx.project_id)
    try:
        await inspection.recording_command(
            "start-document-a",
            action="start",
            session_id="same-session",
            project_id=ctx.project_id,
            document_id="draft-a",
        )
        with pytest.raises(WorkflowRunError) as changed:
            await inspection.recording_command(
                "start-document-b",
                action="start",
                session_id="same-session",
                project_id=ctx.project_id,
                document_id="draft-b",
            )
        assert changed.value.status == 409
        assert (
            sum(item["command"] == "recorder_start" for item in workers.commands) == 1
        )
    finally:
        await inspection.stop_recording(
            "same-session", after_seq=0, project_id=ctx.project_id
        )
        await inspection.close(opened["sessionId"], project_id=ctx.project_id)


@pytest.mark.asyncio
async def test_failed_start_receipt_keeps_project_owner_without_session(
    scoped_inspection,
):
    ctx, other, inspection, _, _, _ = scoped_inspection
    with pytest.raises(WorkflowRunError):
        await inspection.recording_command(
            "no-browser",
            action="start",
            session_id="not-created",
            project_id=ctx.project_id,
        )
    receipt = inspection.recording_command_status(
        "no-browser", project_id=ctx.project_id
    )
    assert (
        receipt["status"] == "failed"
        and receipt["errorCode"] == "INSPECTION_BROWSER_CLOSED"
    )
    with pytest.raises(WorkflowRunError) as foreign:
        inspection.recording_command_status("no-browser", project_id=other)
    assert foreign.value.status == 404
    with ctx.factory() as session:
        assert session.get(WorkflowRecordingSessionRow, "not-created") is None
        assert (
            session.get(WorkflowRecordingCommandRow, "no-browser").project_id
            == ctx.project_id
        )


def test_unsaved_review_project_owner_revision_and_saved_document_scope(
    scoped_inspection,
):
    ctx, other, inspection, recordings, _, _ = scoped_inspection
    own = ctx.project_id
    request = {
        "expectedRevision": 0,
        "autoWait": True,
        "events": [{"sequence": 1, "type": "click", "selector": "#own"}],
    }
    saved = inspection.save_recording_review("unsaved", request, project_id=own)
    assert (
        SqlAlchemyWorkflowRecordings(ctx.factory).read_review("unsaved", project_id=own)
        == saved
    )
    for foreign in (other, None):
        with pytest.raises(WorkflowRunError):
            inspection.read_recording_review("unsaved", project_id=foreign)
        with pytest.raises(WorkflowRunError):
            inspection.save_recording_review(
                "unsaved", {**request, "expectedRevision": 1}, project_id=foreign
            )
    assert recordings.read_review("unsaved", project_id=own)["revision"] == 1
    with pytest.raises(WorkflowRunError) as conflict:
        inspection.save_recording_review("unsaved", request, project_id=own)
    assert conflict.value.code == "RECORDING_REVIEW_CONFLICT"
    with ctx.factory() as session:
        session.add(
            WorkflowDocumentRow(
                id="foreign-document",
                name="另一项目文档",
                document={"projectId": other},
                layout={},
                revision=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()
    with pytest.raises(WorkflowRunError) as wrong_document:
        inspection.save_recording_review("foreign-document", request, project_id=own)
    assert wrong_document.value.code == "RECORDING_DOCUMENT_SCOPE"
    with ctx.factory() as session:
        assert session.get(WorkflowRecordingReviewRow, "foreign-document") is None
    ctx.archive_to_settled()
    assert inspection.read_recording_review("unsaved", project_id=own) == saved
    with pytest.raises(ProjectError):
        inspection.save_recording_review(
            "unsaved", {**request, "expectedRevision": 1}, project_id=own
        )


def test_recording_scope_migration_preserves_legacy_rows_without_guessing_owner(
    tmp_path,
):
    database = tmp_path / "legacy-recordings.sqlite"
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "0019_recording_commands")
    event = {"type": "input", "selector": "#legacy", "value": "旧原文", "sequence": 1}
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO workflow_recording_sessions VALUES (?,?,?,?,?,?,?)",
            ("legacy", "stopped", None, 1, 20, "2026-09-20", "2026-09-20"),
        )
        connection.execute(
            "INSERT INTO workflow_recording_events VALUES (?,?,?,?)",
            ("legacy", 1, json.dumps(event), 20),
        )
        connection.execute(
            "INSERT INTO workflow_recording_reviews VALUES (?,?,?,?,?)",
            ("old-document", 2, True, json.dumps([event]), "2026-09-20"),
        )
        connection.execute(
            "INSERT INTO workflow_recording_commands VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "old-command",
                "legacy",
                "stop",
                "a" * 64,
                "completed",
                json.dumps({"success": True}),
                200,
                "2026-09-20",
                "2026-09-20",
            ),
        )
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        repo = SqlAlchemyWorkflowRecordings(factory)
        assert repo.events("legacy", after_seq=0)["data"] == [event]
        assert repo.read_review("old-document")["events"] == [event]
        assert repo.read_review("old-document")["revision"] == 2
        assert repo.command("old-command")["payload"] == {"success": True}
        with factory() as session:
            for model in (
                WorkflowRecordingSessionRow,
                WorkflowRecordingReviewRow,
                WorkflowRecordingCommandRow,
            ):
                assert all(
                    row.project_id is None for row in session.scalars(select(model))
                )
            assert (
                session.get(WorkflowRecordingSessionRow, "legacy").document_id is None
            )
        with sqlite3.connect(database) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("0022_merge_studio_pm10",)
    finally:
        factory.dispose()


@pytest.mark.asyncio
async def test_worker_exit_retains_owned_recording_tail_and_unblocks_archive(
    scoped_inspection,
):
    ctx, other, inspection, recordings, workers, resources = scoped_inspection
    own = ctx.project_id
    opened = await inspection.open(profile_id="profile-1", project_id=own)
    await inspection.recording_command(
        "before-exit",
        action="start",
        session_id="exit-record",
        project_id=own,
        document_id="exit-draft",
    )
    workers.recorded.append(
        {"type": "input", "selector": "#kept", "value": "已确认步骤"}
    )
    confirmed = await inspection.recording_events(
        "exit-record", after_seq=0, project_id=own
    )
    assert confirmed["nextSeq"] == 1
    ctx.archive()
    ctx.repository.advance(own)
    assert ctx.state() == "closing"
    await workers.stop(
        opened["sessionId"]
    )  # Existing protocol double emits on_worker_exit.
    assert resources.owner_id is None and inspection.project_blockers(own) == []
    with ctx.factory() as session:
        record = session.get(WorkflowRecordingSessionRow, "exit-record")
        assert record.project_id == own and record.document_id == "exit-draft"
        assert record.status == "interrupted" and record.active_slot is None
    restored = SqlAlchemyWorkflowRecordings(ctx.factory)
    assert (
        restored.events("exit-record", after_seq=0, project_id=own)["data"][0]["value"]
        == "已确认步骤"
    )
    with pytest.raises(WorkflowRunError):
        restored.events("exit-record", after_seq=0, project_id=other)
    ctx.repository.advance(own)
    assert ctx.state() == "archived"
    assert recordings.command("before-exit", project_id=own)["status"] == "completed"


def inspection_http_client(service: WorkflowInspectionService) -> httpx.AsyncClient:
    """Real HTTP handlers and SQL ownership, controlled worker protocol only."""
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_inspection_router(service))
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("omit_project", [False, True])
async def test_http_scope_isolates_browser_picker_recording_and_review(
    scoped_inspection, omit_project
):
    ctx, other, inspection, recordings, workers, resources = scoped_inspection
    own = {"projectId": ctx.project_id}
    foreign = {} if omit_project else {"projectId": other}
    async with inspection_http_client(inspection) as client:
        opened = await client.post(
            "/api/browser/open", params=own, json={"profileId": "profile-1"}
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["sessionId"]
        for route in ("/api/browser/status", "/api/browser/pages"):
            response = await client.get(route, params=own)
            assert response.status_code == 200, response.text
        commands_before = list(workers.commands)
        for method, route, body in (
            ("GET", "/api/browser/status", None),
            ("GET", "/api/browser/pages", None),
            ("GET", "/api/browser/url", None),
            ("GET", "/api/element-picker/status", None),
            ("GET", "/api/element-picker/result", None),
            ("POST", "/api/browser/close", {"sessionId": session_id}),
            ("POST", "/api/browser/navigate", {"url": "https://other.test"}),
            (
                "POST",
                "/api/element-picker/start",
                {"sessionId": "foreign-picker", "profileId": "profile-1"},
            ),
            ("POST", "/api/element-picker/test-selector", {"selector": "#target"}),
        ):
            response = await client.request(method, route, params=foreign, json=body)
            assert response.status_code == 404, (route, response.text)
            assert response.json()["error"]["code"] == "INSPECTION_NOT_FOUND"
        assert workers.commands == commands_before
        assert workers.busy() and resources.owner_id == session_id
        start_body = {
            "sessionId": "http-record",
            "commandId": "http-start",
            "documentId": "http-draft",
        }
        started = await client.post("/api/recorder/start", params=own, json=start_body)
        assert started.status_code == 200, started.text
        workers.recorded.append({"type": "click", "selector": "#project-private"})
        events = await client.get(
            "/api/recorder/events", params={**own, "sessionId": "http-record"}
        )
        assert events.status_code == 200 and events.json()["nextSeq"] == 1
        review_body = {
            "expectedRevision": 0,
            "autoWait": True,
            "events": events.json()["data"],
        }
        review = await client.put(
            "/api/recorder/reviews/http-draft", params=own, json=review_body
        )
        assert review.status_code == 200, review.text
        commands_before = list(workers.commands)
        empty = await client.get("/api/recorder/status", params=foreign)
        assert empty.status_code == 200
        assert empty.json() == {
            "success": True,
            "sessionId": None,
            "recording": False,
            "paused": False,
            "nextSeq": 0,
        }
        for route, params in (
            ("/api/recorder/commands/http-start", foreign),
            ("/api/recorder/reviews/http-draft", foreign),
            ("/api/recorder/events", {**foreign, "sessionId": "http-record"}),
        ):
            response = await client.get(route, params=params)
            assert response.status_code == 404, (route, response.text)
            assert "#project-private" not in response.text
        replay = await client.post(
            "/api/recorder/start", params=foreign, json=start_body
        )
        assert replay.status_code == 404, replay.text
        overwrite = await client.put(
            "/api/recorder/reviews/http-draft",
            params=foreign,
            json={**review_body, "expectedRevision": 1, "events": []},
        )
        assert overwrite.status_code == 404, overwrite.text
        foreign_stop = await client.post(
            "/api/recorder/stop",
            params=foreign,
            json={"sessionId": "http-record", "commandId": "foreign-stop"},
        )
        assert foreign_stop.status_code == 409, foreign_stop.text
        assert foreign_stop.json()["error"]["code"] == "INSPECTION_SESSION_CONFLICT"
        assert workers.commands == commands_before
        assert (
            recordings.read_review("http-draft", project_id=ctx.project_id)["revision"]
            == 1
        )
        status = await client.get("/api/recorder/status", params=own)
        assert status.status_code == 200 and status.json()["sessionId"] == "http-record"
        assert status.json()["recording"] is True
        stopped = await client.post(
            "/api/recorder/stop",
            params=own,
            json={"sessionId": "http-record", "commandId": "http-stop"},
        )
        assert stopped.status_code == 200, stopped.text
        closed = await client.post(
            "/api/browser/close", params=own, json={"sessionId": session_id}
        )
        assert closed.status_code == 200, closed.text
        assert resources.owner_id is None and not workers.busy()


@pytest.mark.asyncio
async def test_http_closing_allows_reads_cleanup_but_blocks_start_resume_review_write(
    scoped_inspection,
):
    ctx, _, inspection, _, workers, resources = scoped_inspection
    own = {"projectId": ctx.project_id}
    async with inspection_http_client(inspection) as client:
        opened = await client.post(
            "/api/browser/open", params=own, json={"profileId": "profile-1"}
        )
        assert opened.status_code == 200, opened.text
        started = await client.post(
            "/api/recorder/start",
            params=own,
            json={"sessionId": "closing-record", "commandId": "closing-start"},
        )
        assert started.status_code == 200, started.text
        review = await client.put(
            "/api/recorder/reviews/closing-draft",
            params=own,
            json={"expectedRevision": 0, "autoWait": True, "events": []},
        )
        assert review.status_code == 200, review.text
        workers.recorded.append({"type": "input", "selector": "#tail", "value": "收尾"})
        ctx.archive()
        ctx.repository.advance(ctx.project_id)
        assert ctx.state() == "closing"
        for route in (
            "/api/browser/status",
            "/api/browser/pages",
            "/api/recorder/status",
            "/api/recorder/commands/closing-start",
            "/api/recorder/reviews/closing-draft",
        ):
            response = await client.get(route, params=own)
            assert response.status_code == 200, (route, response.text)
        commands_before = list(workers.commands)
        for method, route, body in (
            ("POST", "/api/browser/open", {"profileId": "profile-1"}),
            (
                "POST",
                "/api/element-picker/start",
                {"profileId": "profile-1", "sessionId": "late-picker"},
            ),
            (
                "POST",
                "/api/recorder/start",
                {"sessionId": "late-record", "commandId": "late-start"},
            ),
            (
                "POST",
                "/api/recorder/resume",
                {"sessionId": "closing-record", "commandId": "late-resume"},
            ),
            (
                "PUT",
                "/api/recorder/reviews/closing-draft",
                {"expectedRevision": 1, "autoWait": False, "events": []},
            ),
        ):
            response = await client.request(method, route, params=own, json=body)
            assert response.status_code == 423, (route, response.text)
            assert response.json()["error"]["code"] == "PROJECT_CLOSING"
        assert workers.commands == commands_before
        stopped = await client.post(
            "/api/recorder/stop",
            params=own,
            json={"sessionId": "closing-record", "commandId": "closing-stop"},
        )
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["nextSeq"] == 1
        tail = await client.get(
            "/api/recorder/events", params={**own, "sessionId": "closing-record"}
        )
        assert tail.status_code == 200 and tail.json()["data"][0]["value"] == "收尾"
        ctx.repository.advance(ctx.project_id)
        assert ctx.state() == "closing" and resources.owner_id is not None
        closed = await client.post(
            "/api/browser/close",
            params=own,
            json={"sessionId": opened.json()["sessionId"]},
        )
        assert closed.status_code == 200, closed.text
        ctx.repository.advance(ctx.project_id)
        assert ctx.state() == "archived" and resources.owner_id is None
