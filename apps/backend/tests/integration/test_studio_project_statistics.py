"""Persisted Studio facts, separate from project task-run statistics."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_statistics import project_statistics_router
from autoflow.application.projects.statistics import ProjectStatisticsService
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.runs import WorkflowRunStart
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns

BASE = datetime(2026, 9, 20, 4, tzinfo=UTC)


@pytest.fixture
def studio_stats(tmp_path):
    path = tmp_path / "statistics.sqlite"
    migrate_database(path)
    factory = create_session_factory(path)
    own, other = str(uuid4()), str(uuid4())
    with factory() as session:
        for identifier in (own, other):
            session.add(
                ProjectRow(
                    id=identifier,
                    name=identifier,
                    name_key=identifier,
                    description="",
                    search_text="",
                    default_resources={},
                    management_revision=1,
                    lifecycle_state="active",
                    created_at=BASE,
                    updated_at=BASE,
                )
            )
        session.commit()
    repo = SqlAlchemyWorkflowRuns(factory)
    for index, (project, status) in enumerate(
        (
            (own, "completed"),
            (other, "completed"),
            (own, "failed"),
            (own, "stopped"),
            (own, "interrupted"),
        )
    ):
        run_id = f"run-{index}"
        start = WorkflowRunStart(
            run_id,
            "flow",
            "flow",
            "真实统计流程",
            {"nodes": []},
            {},
            "profile",
            {},
            "debug" if index == 2 else "run",
            project_id=project,
        )
        repo.create(start, request_hash=run_id, now=BASE + timedelta(minutes=index))
        if index in (0, 1):
            for iteration in range(2):
                repo.append_event(
                    run_id,
                    "execution:node_start",
                    {},
                    now=BASE,
                    node_id="extract",
                    execution_id=f"exec-{iteration}",
                )
                repo.append_event(
                    run_id,
                    "execution:node-succeeded",
                    {"result": {"data": {"value": "x" * 70000}}},
                    now=BASE,
                    node_id="extract",
                    execution_id=f"exec-{iteration}",
                )
            for artifact, purpose in [("png", "result"), ("vars", "diagnostic")]:
                repo.register_artifact(
                    run_id=run_id,
                    artifact_id=artifact,
                    node_id="extract",
                    execution_id="exec-1",
                    relative_path=f"{artifact}.dat",
                    size=8,
                    sha256="a" * 64,
                    mime_type="application/json",
                    purpose=purpose,
                )
        if index == 2:
            repo.append_event(
                run_id,
                "execution:node_start",
                {},
                now=BASE,
                node_id="failure",
                execution_id="failed-exec",
            )
            repo.append_event(
                run_id,
                "execution:node-failed",
                {"error": "private error"},
                now=BASE,
                node_id="failure",
                execution_id="failed-exec",
            )
        repo.finish(
            run_id,
            status=status,
            error=None,
            terminal_log=None,
            now=BASE + timedelta(minutes=index, seconds=10),
        )
        repo.finish(
            run_id,
            status=status,
            error=None,
            terminal_log=None,
            now=BASE + timedelta(days=1),
        )
    yield factory, own, other
    factory.dispose()


def test_statistics_counts_persisted_executions_once_and_pages_without_foreign_data(
    studio_stats,
):
    factory, own, _ = studio_stats
    service = ProjectStatisticsService(factory)
    window = {"from_": BASE, "to": BASE + timedelta(hours=1)}
    value = service.studio(own, **window, limit=2)
    assert value["totalRuns"] == 4
    assert value["byStatus"] == {
        "completed": 1,
        "failed": 1,
        "stopped": 1,
        "interrupted": 1,
    }
    assert value["successRate"] == 0.5 and value["averageDurationMs"] == 10000
    assert value["nodeExecutionCount"] == 3 and value["extractionExecutionCount"] == 2
    assert (
        value["artifactCount"] == value["diagnosticCount"] == value["debugCount"] == 1
    )
    assert value["failuresByNode"] == [{"nodeId": "failure", "count": 1}]
    assert value["runsByWorkflow"] == [
        {"workflowId": "flow", "name": "真实统计流程", "count": 4}
    ]
    assert value["byTrigger"] == {"unknown": 4}
    assert value["recordingCount"] == 0 and value["recordingUnavailableReason"] is None
    assert [item["runId"] for item in value["items"]] == ["run-4", "run-3"] and value[
        "nextCursor"
    ] == 2
    assert "private error" not in str(value) and "x" * 1000 not in str(value)
    second = service.studio(own, **window, cursor=2, limit=2)
    assert [item["runId"] for item in second["items"]] == ["run-2", "run-0"] and second[
        "nextCursor"
    ] is None
    assert (
        ProjectStatisticsService(factory).studio(own, **window)["nodeExecutionCount"]
        == 3
    )


def test_statistics_filters_before_aggregation_and_validates_project_and_range(
    studio_stats,
):
    factory, own, _ = studio_stats
    service = ProjectStatisticsService(factory)
    result = service.studio(
        own,
        from_=BASE + timedelta(minutes=2),
        to=BASE + timedelta(minutes=3),
        status="failed",
        workflow_id="flow",
    )
    assert (
        result["totalRuns"] == result["debugCount"] == result["nodeExecutionCount"] == 1
    )
    empty = service.studio(
        own, workflow_id="foreign", from_=BASE, to=BASE + timedelta(hours=1)
    )
    assert (
        empty["totalRuns"] == 0
        and empty["successRate"] is None
        and empty["averageDurationMs"] is None
    )
    assert empty["latestActivityAt"] is None and empty["items"] == []
    for changes in (
        {"status": "invented"},
        {"cursor": -1},
        {"limit": 201},
        {"from_": BASE, "to": BASE - timedelta(seconds=1)},
    ):
        with pytest.raises(ProjectError):
            service.studio(own, **changes)
    with factory() as session:
        session.get(ProjectRow, own).lifecycle_state = "archived"
        session.commit()
    assert (
        service.studio(own, from_=BASE, to=BASE + timedelta(hours=1))["totalRuns"] == 4
    )
    with factory() as session:
        session.get(ProjectRow, own).lifecycle_state = "deleted"
        session.commit()
    with pytest.raises(ProjectError):
        service.studio(own)


def test_statistics_http_contract_and_project_filter(studio_stats):
    factory, own, other = studio_stats
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(project_statistics_router(ProjectStatisticsService(factory)))
    with TestClient(app) as client:
        query = {
            "from": BASE.isoformat(),
            "to": (BASE + timedelta(hours=1)).isoformat(),
            "limit": 1,
        }
        response = client.get(f"/api/v1/projects/{own}/statistics/studio", params=query)
        assert response.status_code == 200, response.text
        body = response.json()
        assert (
            body["projectId"] == own
            and body["totalRuns"] == 4
            and len(body["items"]) == 1
            and body["recordingCount"] == 0
        )
        other_body = client.get(
            f"/api/v1/projects/{other}/statistics/studio", params=query
        ).json()
        assert (
            other_body["totalRuns"] == 1 and other_body["items"][0]["runId"] == "run-1"
        )
        assert (
            client.get(
                f"/api/v1/projects/{own}/statistics/studio?status=invented"
            ).status_code
            == 422
        )


def _start_run(
    factory,
    project_id,
    run_id,
    *,
    workflow_id="additional-flow",
    started_at=BASE,
    mode="run",
):
    repo = SqlAlchemyWorkflowRuns(factory)
    start = WorkflowRunStart(
        run_id,
        workflow_id,
        workflow_id,
        "追加事实",
        {"nodes": []},
        {},
        "profile",
        {},
        mode,
        project_id=project_id,
    )
    repo.create(start, request_hash=run_id, now=started_at)
    return repo


def test_statistics_joins_persisted_schedule_sources_without_multiplying_runs(
    studio_stats,
):
    from autoflow.infrastructure.database.workflow_schedules import (
        SqlAlchemyWorkflowSchedules,
    )

    factory, own, _ = studio_stats
    schedules = SqlAlchemyWorkflowSchedules(factory)
    for index, (run_id, trigger) in enumerate(
        (
            ("run-0", "time"),
            ("run-0", "time"),
            ("run-2", "webhook"),
            ("run-1", "hotkey"),
        )
    ):
        task_id, execution_id = str(uuid4()), str(uuid4())
        schedules.create(
            task_id,
            {"workflow_id": "flow", "name": f"task-{index}", "enabled": True},
            BASE,
        )
        command = f"command-{index}"
        log = {
            "id": execution_id,
            "task_id": task_id,
            "trigger_type": trigger,
            "run_id": None,
        }
        _, created = schedules.enqueue_execution(
            task_id, execution_id, command, log, BASE
        )
        assert created
        assert schedules.claim_next(BASE)["id"] == execution_id
        schedules.attach_run(
            execution_id, run_id=run_id, run_status="completed", now=BASE
        )
        schedules.finish_execution(
            execution_id, status="success", error=None, run_id=run_id, now=BASE
        )
        _, duplicate = schedules.enqueue_execution(
            task_id, execution_id, command, log, BASE
        )
        assert duplicate is False
    value = ProjectStatisticsService(factory).studio(
        own, from_=BASE, to=BASE + timedelta(hours=1), limit=1
    )
    assert value["byTrigger"] == {"time": 1, "webhook": 1, "unknown": 2}
    assert value["totalRuns"] == sum(value["byTrigger"].values()) == 4
    assert value["nodeExecutionCount"] == 3
    assert len(value["items"]) == 1


def test_statistics_refreshes_active_terminal_and_rebuilt_service_from_sqlite(
    studio_stats,
):
    factory, own, _ = studio_stats
    repo = _start_run(factory, own, "active-debug", mode="debug")
    service = ProjectStatisticsService(factory)
    window = {
        "from_": BASE,
        "to": BASE + timedelta(hours=1),
        "workflow_id": "additional-flow",
    }
    first = service.studio(own, **window)
    assert first["byStatus"] == {"starting": 1}
    assert first["successRate"] is None and first["averageDurationMs"] is None
    assert first["debugCount"] == 1 and first["items"][0]["finishedAt"] is None
    repo.append_event(
        "active-debug",
        "execution:paused",
        {"pauseId": "pause-1"},
        now=BASE + timedelta(seconds=1),
        run_patch={"status": "paused"},
    )
    paused = ProjectStatisticsService(factory).studio(own, **window)
    assert paused["byStatus"] == {"paused": 1}
    assert datetime.fromisoformat(paused["latestActivityAt"]) == BASE + timedelta(
        seconds=1
    )
    assert paused["nodeExecutionCount"] == 0
    repo.append_event(
        "active-debug",
        "execution:node_start",
        {},
        now=BASE + timedelta(seconds=2),
        node_id="one",
        execution_id="one-1",
    )
    repo.finish(
        "active-debug",
        status="failed",
        error={"message": "sensitive-do-not-expose"},
        terminal_log=None,
        now=BASE + timedelta(seconds=3),
    )
    finished = service.studio(own, **window)
    rebuilt = ProjectStatisticsService(factory).studio(own, **window)
    for value in (finished, rebuilt):
        assert value["byStatus"] == {"failed": 1}
        assert value["successRate"] == 0 and value["averageDurationMs"] == 3000
        assert value["nodeExecutionCount"] == 1 and value["debugCount"] == 1
        assert datetime.fromisoformat(
            value["items"][0]["finishedAt"]
        ) == BASE + timedelta(seconds=3)
        assert "sensitive-do-not-expose" not in str(value)
        assert value["recordingCount"] == 0
    assert service.studio(own, **window, status="paused")["totalRuns"] == 0


@pytest.mark.parametrize("ownership", ["top-level", "content", "automation-binding"])
def test_statistics_resolves_legacy_saved_document_project_without_claiming_unbound_runs(
    studio_stats, ownership
):
    from autoflow.infrastructure.database.project_automation_models import (
        ProjectAutomationRow,
    )
    from autoflow.infrastructure.database.workflow_models import (
        WorkflowDocumentRow,
        WorkflowRunRow,
    )

    factory, own, other = studio_stats
    document = (
        {"projectId": own}
        if ownership == "top-level"
        else {"content": {"projectId": own}}
        if ownership == "content"
        else {}
    )
    with factory() as session:
        session.add(
            WorkflowDocumentRow(
                id="legacy-flow",
                name="旧文档",
                document=document,
                layout={},
                revision=1,
                created_at=BASE,
                updated_at=BASE,
            )
        )
        session.flush()
        if ownership == "automation-binding":
            session.add(
                ProjectAutomationRow(
                    id=str(uuid4()),
                    project_id=own,
                    workflow_id="legacy-flow",
                    name="旧自动化",
                    name_key="legacy",
                    search_text="",
                    description="",
                    management_revision=1,
                    input_plan={},
                    parameter_schema=[],
                    environment_policy={},
                    run_policy={},
                    created_at=BASE,
                    updated_at=BASE,
                )
            )
        session.commit()
    for run_id, project_id, workflow_id in [
        ("legacy-run", own, "legacy-flow"),
        ("unbound-run", None, "unbound-flow"),
    ]:
        repo = _start_run(factory, project_id, run_id, workflow_id=workflow_id)
        repo.finish(
            run_id,
            status="completed",
            error=None,
            terminal_log=None,
            now=BASE + timedelta(seconds=1),
        )
        with factory() as session:
            row = session.get(WorkflowRunRow, run_id)
            row.payload = {
                key: value for key, value in row.payload.items() if key != "projectId"
            }
            session.commit()
    service = ProjectStatisticsService(factory)
    window = {"from_": BASE, "to": BASE + timedelta(hours=1)}
    own_ids = {item["runId"] for item in service.studio(own, **window)["items"]}
    other_ids = {item["runId"] for item in service.studio(other, **window)["items"]}
    assert own_ids == {"run-0", "run-2", "run-3", "run-4", "legacy-run"}
    assert other_ids == {"run-1"}
    assert "unbound-run" not in own_ids | other_ids


@pytest.mark.parametrize("offset_hours", [0, 8, -5])
def test_statistics_inclusive_millisecond_boundaries_use_absolute_instants(
    studio_stats, offset_hours
):
    from datetime import timezone

    factory, own, _ = studio_stats
    zone = timezone(timedelta(hours=offset_hours))
    for index in range(4):
        started = (BASE + timedelta(milliseconds=index)).astimezone(zone)
        repo = _start_run(
            factory,
            own,
            f"millisecond-{index}",
            workflow_id="milliseconds",
            started_at=started,
        )
        repo.finish(
            f"millisecond-{index}",
            status="completed",
            error=None,
            terminal_log=None,
            now=started + timedelta(milliseconds=7),
        )
    service = ProjectStatisticsService(factory)
    result = service.studio(
        own,
        workflow_id="milliseconds",
        from_=BASE + timedelta(milliseconds=1),
        to=BASE + timedelta(milliseconds=2),
    )
    assert result["totalRuns"] == 2
    assert [item["runId"] for item in result["items"]] == [
        "millisecond-2",
        "millisecond-1",
    ]
    assert result["averageDurationMs"] == 7
    clipped = service.studio(
        own,
        workflow_id="milliseconds",
        from_=BASE,
        to=BASE + timedelta(hours=1),
        now=BASE + timedelta(milliseconds=1),
    )
    assert clipped["totalRuns"] == 2
    assert datetime.fromisoformat(clipped["to"]) == BASE + timedelta(milliseconds=1)


def _offset_runs(factory, project):
    from datetime import timezone

    older = (BASE - timedelta(hours=3)).astimezone(timezone(timedelta(hours=8)))
    newer = BASE - timedelta(hours=2)
    for run_id, started in [("older-offset", older), ("newer-utc", newer)]:
        repo = _start_run(
            factory, project, run_id, workflow_id="offset-order", started_at=started
        )
        repo.finish(
            run_id,
            status="completed",
            error=None,
            terminal_log=None,
            now=started + timedelta(milliseconds=123),
        )
    return {
        "workflow_id": "offset-order",
        "from_": BASE - timedelta(hours=4),
        "to": BASE,
    }


def test_statistics_pages_mixed_offsets_by_actual_start_time(studio_stats):
    factory, own, _ = studio_stats
    window = _offset_runs(factory, own)
    service = ProjectStatisticsService(factory)
    first = service.studio(own, **window, limit=1)
    second = service.studio(own, **window, limit=1, cursor=first["nextCursor"])
    assert first["items"][0]["runId"] == "newer-utc"
    assert second["items"][0]["runId"] == "older-offset"
    assert second["nextCursor"] is None
    assert first["averageDurationMs"] == 123


def test_statistics_latest_activity_compares_offsets_as_instants(studio_stats):
    factory, own, _ = studio_stats
    window = _offset_runs(factory, own)
    service = ProjectStatisticsService(factory)
    result = service.studio(own, **window)
    assert datetime.fromisoformat(result["latestActivityAt"]) == BASE - timedelta(
        hours=2
    ) + timedelta(milliseconds=123)
    active = _start_run(
        factory,
        own,
        "active-event",
        workflow_id="offset-order",
        started_at=BASE - timedelta(hours=4),
    )
    active.append_event(
        "active-event",
        "execution:log",
        {"message": "later diagnostic"},
        now=BASE - timedelta(hours=1),
    )
    refreshed = service.studio(own, **window)
    assert datetime.fromisoformat(refreshed["latestActivityAt"]) == BASE - timedelta(
        hours=1
    )


def test_statistics_thousand_iterations_count_all_persisted_events_across_pages(
    studio_stats,
):
    factory, own, _ = studio_stats
    repo = _start_run(factory, own, "loop-run", workflow_id="loop-flow")
    for index in range(1000):
        moment = BASE + timedelta(milliseconds=index)
        repo.append_event(
            "loop-run",
            "execution:node_start",
            {},
            now=moment,
            node_id="extract",
            execution_id=f"iteration-{index}",
        )
        repo.append_event(
            "loop-run",
            "execution:node-succeeded",
            {"result": {"data": {"index": index}}},
            now=moment,
            node_id="extract",
            execution_id=f"iteration-{index}",
        )
    repo.finish(
        "loop-run",
        status="completed",
        error=None,
        terminal_log=None,
        now=BASE + timedelta(seconds=1),
    )
    seen = []
    after = 0
    while True:
        batch = repo.list_events("loop-run", after, 137)
        if not batch:
            break
        seen.extend(batch)
        assert all(event.sequence > after for event in batch)
        after = batch[-1].sequence
    assert [event.sequence for event in seen] == list(range(1, 2002))
    outputs = [event for event in seen if event.type == "execution:node-succeeded"]
    assert [event.payload["result"]["data"]["index"] for event in outputs] == list(
        range(1000)
    )
    assert len({event.execution_id for event in outputs}) == 1000
    value = ProjectStatisticsService(factory).studio(
        own, from_=BASE, to=BASE + timedelta(hours=1), workflow_id="loop-flow", limit=1
    )
    assert value["totalRuns"] == 1 and value["byStatus"] == {"completed": 1}
    assert value["nodeExecutionCount"] == value["extractionExecutionCount"] == 1000
    assert value["artifactCount"] == value["diagnosticCount"] == 0
    assert value["recordingCount"] == 0 and value["nextCursor"] is None
    assert len(str(value)) < 3000


@pytest.mark.asyncio
async def test_statistics_counts_actual_worker_published_node_starts(
    studio_stats, tmp_path
):
    """Do not invent event names: run the production worker/runtime and persist its wire events."""
    import asyncio

    from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager

    factory, own, _ = studio_stats
    repo = _start_run(factory, own, "worker-statistics", workflow_id="worker-flow")
    received = []

    def persist_wire_event(event):
        received.append(event)
        if not str(event.get("type", "")).startswith("execution:"):
            return
        repo.append_event(
            "worker-statistics",
            event["type"],
            {
                key: value
                for key, value in event.items()
                if key not in {"type", "runId", "workflowId", "nodeId", "executionId"}
            },
            now=BASE + timedelta(seconds=1),
            node_id=event.get("nodeId"),
            execution_id=event.get("executionId"),
        )

    manager = WorkflowWorkerManager(tmp_path, on_event=persist_wire_event)
    nodes = [
        {
            "id": "first",
            "type": "moduleNode",
            "data": {
                "moduleType": "set_variable",
                "config": {"variableName": "first", "variableValue": "1"},
            },
        },
        {
            "id": "second",
            "type": "moduleNode",
            "data": {
                "moduleType": "set_variable",
                "config": {"variableName": "second", "variableValue": "{first} + 1"},
            },
        },
    ]
    try:
        await manager.start(
            "worker-statistics",
            "profile",
            None,
            {
                "runId": "worker-statistics",
                "workflowId": "worker-flow",
                "profileId": "profile",
                "requiresBrowser": False,
                "artifactRoot": str(tmp_path / "worker-artifacts"),
                "document": {
                    "nodes": nodes,
                    "edges": [{"id": "next", "source": "first", "target": "second"}],
                    "variables": [],
                },
            },
        )
        async with asyncio.timeout(15):
            while manager.busy():
                await asyncio.sleep(0.02)
        assert manager.active_processes() == []
        starts = [
            event for event in received if event.get("type") == "execution:node_start"
        ]
        completions = [
            event
            for event in received
            if event.get("type") == "execution:node_complete"
        ]
        assert [event["nodeId"] for event in starts] == ["first", "second"]
        assert len({event["executionId"] for event in starts}) == 2
        assert [event["success"] for event in completions] == [True, True]
        assert [event["data"] for event in completions] == [1, 2]
        assert any(event.get("type") == "execution:completed" for event in received)
        repo.finish(
            "worker-statistics",
            status="completed",
            error=None,
            terminal_log=None,
            now=BASE + timedelta(seconds=2),
        )
        persisted = repo.list_events("worker-statistics", 0, 100)
        assert sum(event.type == "execution:node_start" for event in persisted) == 2
        result = ProjectStatisticsService(factory).studio(
            own, from_=BASE, to=BASE + timedelta(hours=1), workflow_id="worker-flow"
        )
        assert result["totalRuns"] == 1 and result["byStatus"] == {"completed": 1}
        assert result["nodeExecutionCount"] == 2
        assert result["recordingCount"] == 0
    finally:
        await manager.shutdown()


def test_statistics_counts_owned_recording_sessions_not_commands_or_legacy_guesses(
    studio_stats,
):
    from autoflow.infrastructure.database.workflow_recordings import (
        SqlAlchemyWorkflowRecordings,
    )

    factory, own, other = studio_stats
    repo = SqlAlchemyWorkflowRecordings(factory)
    records = [
        ("own-a", own, "draft-a", BASE + timedelta(minutes=10)),
        ("own-b", own, "draft-b", BASE + timedelta(minutes=20)),
        ("foreign-a", other, "draft-a", BASE + timedelta(minutes=30)),
        ("legacy-unbound", None, "draft-a", BASE + timedelta(minutes=40)),
        ("outside-before", own, "draft-a", BASE - timedelta(seconds=1)),
        ("outside-after", own, "draft-a", BASE + timedelta(hours=2)),
    ]
    for session_id, project, document_id, started in records:
        first = repo.start(
            session_id, now=started, project_id=project, document_id=document_id
        )
        assert (
            repo.start(
                session_id, now=started, project_id=project, document_id=document_id
            )
            == first
        )
        for action in ("start", "pause", "resume", "stop"):
            kwargs = {
                "session_id": session_id,
                "action": action,
                "request_hash": action,
                "now": started,
                "project_id": project,
            }
            command_id = f"{session_id}-{action}"
            assert repo.begin_command(command_id, **kwargs) is None
            assert repo.begin_command(command_id, **kwargs)["status"] == "pending"
            repo.finish_command(
                command_id,
                status="completed",
                payload={"success": True},
                http_status=200,
                now=started,
            )
        repo.append(
            session_id,
            [
                {"type": "click", "selector": "#a"},
                {"type": "input", "selector": "#b", "value": "两步不是两次录制"},
            ],
            now=started,
        )
        repo.stop(session_id, now=started + timedelta(seconds=7))
    service = ProjectStatisticsService(factory)
    window = {"from_": BASE, "to": BASE + timedelta(hours=1)}
    value = service.studio(own, **window)
    assert value["recordingCount"] == 2 and value["recordingUnavailableReason"] is None
    assert value["totalRuns"] == 4
    assert datetime.fromisoformat(value["latestActivityAt"]) == BASE + timedelta(
        minutes=20, seconds=7
    )
    scoped = service.studio(own, **window, workflow_id="draft-a")
    assert scoped["recordingCount"] == 1 and scoped["totalRuns"] == 0
    assert datetime.fromisoformat(scoped["latestActivityAt"]) == BASE + timedelta(
        minutes=10, seconds=7
    )
    assert service.studio(other, **window)["recordingCount"] == 1
    assert service.studio(own, **window, workflow_id="missing")["recordingCount"] == 0
    assert (
        service.studio(
            own, from_=BASE + timedelta(minutes=15), to=BASE + timedelta(minutes=25)
        )["recordingCount"]
        == 1
    )
    filtered = service.studio(own, **window, status="failed")
    assert filtered["recordingCount"] is None
    assert filtered["recordingUnavailableReason"] == "运行状态筛选不适用于录制次数"
    rebuilt = ProjectStatisticsService(factory).studio(own, **window)
    assert rebuilt["recordingCount"] == 2
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(project_statistics_router(ProjectStatisticsService(factory)))
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/projects/{own}/statistics/studio",
            params={
                "from": BASE.isoformat(),
                "to": (BASE + timedelta(hours=1)).isoformat(),
                "workflowId": "draft-a",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["recordingCount"] == 1
        assert response.json()["recordingUnavailableReason"] is None
