from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.project_runs import project_runs_router
from autoflow.adapters.http.projects import projects_router
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.projects.overview import ProjectOverviewService
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.environment_models import ProjectManualItemRow
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from autoflow.infrastructure.database.project_runs import SqlAlchemyProjectRuns
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from tests.integration.test_project_run_start import setup, start_payload


class Scheduler:
    def __init__(self):
        self.wakes = 0

    def wake(self):
        self.wakes += 1

    def force_stop_availability(self, _project_id, _batch_id):
        return False, None


def client_for(tmp_path, resolver=None):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path, resolver)
    scheduler = Scheduler()
    app = FastAPI()
    app.include_router(
        projects_router(
            ProjectService(SqlAlchemyProjects(factory)), ProjectOverviewService(factory)
        )
    )
    app.include_router(
        project_runs_router(
            coordinator, ProjectRunQueries(factory), scheduler, QuiesceGate()
        )
    )
    return TestClient(app), factory, project, automation, scheduler


def test_operation_lookup_accepts_every_kind_the_runs_router_can_write(tmp_path):
    """The unknown-result recovery reads the operation back by its key.

    A follow-up Batch writes ``followUpBatch``; if the read schema does not list
    that kind the lookup answers 500 and the UI can never reconcile the command.
    """
    client, factory, project, _automation, _scheduler = client_for(tmp_path)
    key = str(uuid4())
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            ProjectOperationRow(
                id=str(uuid4()),
                project_id=project.project_id,
                idempotency_key=key,
                kind="followUpBatch",
                request_digest="0" * 64,
                status="succeeded",
                status_revision=2,
                resource={
                    "type": "batch",
                    "projectId": project.project_id,
                    "batchId": str(uuid4()),
                },
                result=None,
                created_at=now,
                updated_at=now,
                completed_at=now,
            )
        )
        session.commit()

    response = client.get(
        f"/api/v1/projects/{project.project_id}/operations/by-idempotency-key/{key}"
    )

    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "followUpBatch"


def test_start_returns_accepted_operation_then_wakes_scheduler(tmp_path):
    client, factory, project, automation, scheduler = client_for(tmp_path)
    key = str(uuid4())

    response = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": key},
        json=start_payload(automation, max_tasks=2),
    )

    assert response.status_code == 202
    operation = response.json()["operation"]
    assert operation["idempotencyKey"] == key
    assert operation["kind"] == "startBatch"
    assert operation["result"]["batch"]["createdTaskCount"] == 2
    assert scheduler.wakes == 1
    factory.dispose()


def test_batch_and_task_queries_return_real_counts_snapshots_and_core_run(tmp_path):
    client, factory, project, automation, _ = client_for(tmp_path)
    started = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation, max_tasks=2),
    ).json()["operation"]["result"]["batch"]
    batch_id = started["batchId"]
    with factory.begin() as session:
        current_workflow = session.get(WorkflowDocumentRow, automation.workflow_id)
        assert current_workflow is not None
        changed = dict(current_workflow.document)
        content = dict(changed["content"])
        nodes = [dict(node) for node in content["nodes"]]
        nodes[0] = {**nodes[0], "data": {**nodes[0]["data"], "label": "当前已改名"}}
        current_workflow.document = {**changed, "content": {**content, "nodes": nodes}}

    batches = client.get(
        f"/api/v1/projects/{project.project_id}/batches",
        params={"automationId": automation.automation_id, "status": "accepted"},
    )
    assert batches.status_code == 200
    assert batches.json()["total"] == 1
    assert batches.json()["items"][0]["createdTaskCount"] == 2
    detail = client.get(
        f"/api/v1/projects/{project.project_id}/batches/{batch_id}"
    ).json()
    assert detail["statusCounts"]["queued"] == 2
    assert detail["taskCount"] == 2
    assert detail["stopOperation"] is None
    assert detail["forceStopAllowed"] is False
    assert detail["forceStopAvailableAt"] is None
    assert detail["configurationSnapshot"]["automation"]["name"] == automation.name
    assert (
        detail["configurationSnapshot"]["parameters"][
            "00000000-0000-0000-0000-000000000031"
        ]
        == "每个任务的冻结值"
    )
    assert (
        detail["configurationSnapshot"]["parameters"][
            "00000000-0000-0000-0000-000000000032"
        ]
        is False
    )
    assert detail["configurationSnapshot"]["maxTasks"] == 2
    assert detail["configurationSnapshot"]["concurrency"] == 1
    assert detail["configurationSnapshot"]["workflowRevision"] == 1

    tasks = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch_id, "status": "queued", "pageSize": 1},
    ).json()
    assert tasks["total"] == 2 and len(tasks["items"]) == 1
    assert tasks["items"][0]["taskOrdinal"] in {1, 2}
    assert tasks["items"][0]["automationName"] == automation.name
    assert tasks["items"][0]["inputIdentifier"] == "参数任务"
    assert tasks["items"][0]["batchStartedAt"] == detail["batch"]["createdAt"]
    assert tasks["items"][0]["endNodeName"] is None
    # 排队中的任务没有节点尝试与运行开始，最近状态时间就是任务创建时间，
    # 不能拿客户端时钟或剩余时间伪造一个更「新」的时间。
    assert tasks["items"][0]["lastStatusAt"] == tasks["items"][0]["createdAt"]
    task_id = tasks["items"][0]["taskId"]
    task = client.get(f"/api/v1/projects/{project.project_id}/tasks/{task_id}").json()
    assert task["task"]["status"] == "queued"
    assert task["task"]["taskOrdinal"] == tasks["items"][0]["taskOrdinal"]
    assert task["batchStartedAt"] == detail["batch"]["createdAt"]
    assert task["nodeNames"] == {
        "open": "打开网页",
        "input": "输入文本",
        "click": "点击元素",
        "read": "读取文本",
    }
    assert task["inputSnapshot"]["parameters"]
    assert task["inputSnapshot"]["inputs"] == []
    assert task["run"]["runId"] == task["task"]["runId"]
    assert task["run"]["resourceRequest"] == {
        "browser": "none",
        "modelProviderId": None,
    }
    factory.dispose()


def test_batch_and_task_directories_search_persisted_identifiers_and_frozen_automation_name(
    tmp_path,
):
    client, factory, project, automation, _ = client_for(tmp_path)
    batch = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    ).json()["operation"]["result"]["batch"]
    task = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"][0]

    by_name = client.get(
        f"/api/v1/projects/{project.project_id}/batches", params={"q": automation.name}
    )
    by_batch_id = client.get(
        f"/api/v1/projects/{project.project_id}/batches",
        params={"q": batch["batchId"][4:16]},
    )
    by_task_id = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"q": task["taskId"][4:16]},
    )
    by_task_batch = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"q": batch["batchId"][4:16]},
    )
    by_task_number = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"q": f"任务 {task['taskOrdinal']}"},
    )
    by_task_automation = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"q": automation.name},
    )
    by_task_input = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"q": "每个任务的冻结值"},
    )

    assert by_name.status_code == 200 and by_name.json()["total"] == 1
    assert by_batch_id.status_code == 200 and by_batch_id.json()["total"] == 1
    assert by_task_id.status_code == 200 and by_task_id.json()["total"] == 1
    assert by_task_batch.status_code == 200 and by_task_batch.json()["total"] == 1
    assert by_task_number.status_code == 200
    assert by_task_number.json()["items"][0]["taskOrdinal"] == task["taskOrdinal"]
    assert (
        by_task_automation.status_code == 200
        and by_task_automation.json()["total"] == 1
    )
    assert by_task_input.status_code == 200 and by_task_input.json()["total"] == 1
    assert (
        client.get(
            f"/api/v1/projects/{project.project_id}/batches",
            params={"q": "不存在的自动化"},
        ).json()["total"]
        == 0
    )
    assert (
        client.get(
            f"/api/v1/projects/{project.project_id}/batches", params={"q": "x" * 121}
        ).status_code
        == 422
    )
    factory.dispose()


def test_batch_and_task_search_treats_like_metacharacters_as_literal_text(tmp_path):
    client, factory, project, automation, _ = client_for(tmp_path)
    special = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    ).json()["operation"]["result"]["batch"]
    with factory.begin() as session:
        row = session.get(ProjectBatchRow, special["batchId"])
        assert row is not None
        frozen = dict(row.frozen_request)
        frozen["automation"] = {
            **frozen["automation"],
            "name": "折扣%与下划线_任务",
        }
        row.frozen_request = frozen
    client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    )

    for query in ("%", "_"):
        batches = client.get(
            f"/api/v1/projects/{project.project_id}/batches", params={"q": query}
        )
        tasks = client.get(
            f"/api/v1/projects/{project.project_id}/tasks", params={"q": query}
        )
        assert batches.status_code == tasks.status_code == 200
        assert batches.json()["total"] == 1
        assert tasks.json()["total"] == 1
    factory.dispose()


def test_pagination_and_sort_are_stable(tmp_path):
    client, factory, project, automation, _ = client_for(tmp_path)
    for _ in range(2):
        response = client.post(
            f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
            headers={"Idempotency-Key": str(uuid4())},
            json=start_payload(automation),
        )
        assert response.status_code == 202

    first = client.get(
        f"/api/v1/projects/{project.project_id}/batches",
        params={"page": 1, "pageSize": 1, "sort": "createdAt"},
    ).json()
    second = client.get(
        f"/api/v1/projects/{project.project_id}/batches",
        params={"page": 2, "pageSize": 1, "sort": "createdAt"},
    ).json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["batchId"] != second["items"][0]["batchId"]
    factory.dispose()


def test_queries_do_not_leak_batches_or_tasks_across_project_scope(tmp_path):
    client, factory, project, automation, _ = client_for(tmp_path)
    batch = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    ).json()["operation"]["result"]["batch"]
    queries = ProjectRunQueries(factory)
    other, _, _ = ProjectService(SqlAlchemyProjects(factory)).create(
        str(uuid4()), {"name": "另一项目", "description": ""}
    )
    task_id = queries.list_tasks(project.project_id, batch_id=batch["batchId"])[0][0][
        "taskId"
    ]

    with pytest.raises(ProjectRunError) as missing_project:
        queries.batch_detail(other.project_id, batch["batchId"])
    with pytest.raises(ProjectRunError) as missing_task:
        queries.task_detail(other.project_id, task_id)

    assert missing_project.value.code == missing_task.value.code == "NOT_FOUND"
    factory.dispose()


@pytest.mark.parametrize("collection", ["batches", "tasks"])
def test_unknown_status_and_invalid_time_ranges_are_rejected(tmp_path, collection):
    _, factory, project, _, _ = client_for(tmp_path)
    queries = ProjectRunQueries(factory)
    method = queries.list_batches if collection == "batches" else queries.list_tasks
    prefix = "started" if collection == "batches" else "ended"

    with pytest.raises(ProjectRunError) as unknown:
        method(project.project_id, status="invented")
    with pytest.raises(ProjectRunError) as naive:
        method(
            project.project_id,
            **{f"{prefix}_from": datetime.fromisoformat("2026-01-01T00:00:00")},
        )
    with pytest.raises(ProjectRunError) as reversed_range:
        method(
            project.project_id,
            **{
                f"{prefix}_from": datetime(2026, 1, 2, tzinfo=UTC),
                f"{prefix}_to": datetime(2026, 1, 1, tzinfo=UTC),
            },
        )

    assert (
        unknown.value.status == naive.value.status == reversed_range.value.status == 422
    )
    factory.dispose()


def test_deleted_project_is_not_queryable(tmp_path):
    _, factory, project, _, _ = client_for(tmp_path)
    with factory.begin() as session:
        row = session.get(ProjectRow, project.project_id)
        assert row is not None
        row.lifecycle_state = "deleted"

    with pytest.raises(ProjectRunError) as caught:
        ProjectRunQueries(factory).list_batches(project.project_id)

    assert caught.value.code == "NOT_FOUND"
    factory.dispose()


def test_task_query_projects_only_the_requested_page(tmp_path, monkeypatch):
    client, factory, project, automation, _ = client_for(tmp_path)
    response = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation, max_tasks=3),
    )
    assert response.status_code == 202
    original = SqlAlchemyProjectRuns.task
    projected = 0

    def counted(self, project_id, task_id):
        nonlocal projected
        projected += 1
        return original(self, project_id, task_id)

    monkeypatch.setattr(SqlAlchemyProjectRuns, "task", counted)
    items, total = ProjectRunQueries(factory).list_tasks(
        project.project_id, status="queued", page=2, page_size=1
    )

    assert total == 3 and len(items) == 1
    assert projected == 1
    factory.dispose()


def test_task_detail_recursively_serializes_only_public_resource_snapshot(tmp_path):
    def resources(_automation, _defaults):
        return {
            "browser": "newFromProfile",
            "profileId": "profile-1",
            "kernelId": "public:1",
            "proxy": {"mode": "fixed", "proxyId": "proxy-1"},
            "modelProviderId": None,
            "automaticExecutionTimeoutSeconds": 60,
            "frozenConfiguration": {
                "profileSpec": {"extensionDirectories": ["/private/extension"]}
            },
        }

    client, factory, project, automation, _ = client_for(tmp_path, resources)
    batch = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    ).json()["operation"]["result"]["batch"]
    task_id = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"][0]["taskId"]

    response = client.get(f"/api/v1/projects/{project.project_id}/tasks/{task_id}")

    assert response.status_code == 200
    resource = response.json()["run"]["resourceRequest"]
    assert resource["proxy"] == {"mode": "fixed", "proxyId": "proxy-1"}
    assert resource["automaticExecutionTimeoutSeconds"] == 60
    assert "frozenConfiguration" not in resource
    assert "/private/extension" not in response.text
    factory.dispose()


def test_task_detail_publishes_a_cleanup_summary_on_the_wire(tmp_path):
    """Cleanup is a frozen TaskDetail field; the UI reads it, never guesses it."""
    client, factory, project, automation, _ = client_for(tmp_path)
    batch = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    ).json()["operation"]["result"]["batch"]
    task_id = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"][0]["taskId"]

    cleanup = client.get(
        f"/api/v1/projects/{project.project_id}/tasks/{task_id}"
    ).json()["cleanup"]

    # The synthetic seam resolves ``browser: none``, so nothing is left to clean.
    assert cleanup == {"status": "notRequired", "operationId": None, "message": None}
    factory.dispose()


def test_task_detail_reports_pending_cleanup_for_a_browser_run(tmp_path):
    def resources(_automation, _defaults):
        return {
            "browser": "newFromProfile",
            "profileId": "profile-1",
            "kernelId": "public:1",
            "proxy": {"mode": "none"},
            "modelProviderId": None,
            "frozenConfiguration": {},
        }

    client, factory, project, automation, _ = client_for(tmp_path, resources)
    batch = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    ).json()["operation"]["result"]["batch"]
    task_id = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"][0]["taskId"]

    cleanup = client.get(
        f"/api/v1/projects/{project.project_id}/tasks/{task_id}"
    ).json()["cleanup"]

    assert cleanup["status"] == "pending"
    assert cleanup["operationId"] is None
    assert cleanup["message"]
    factory.dispose()


@pytest.mark.parametrize("path", ["batches", "tasks"])
def test_http_rejects_page_that_cannot_form_a_safe_sql_offset(tmp_path, path):
    client, factory, project, _, _ = client_for(tmp_path)

    response = client.get(
        f"/api/v1/projects/{project.project_id}/{path}",
        params={"page": 10**100},
    )

    assert response.status_code == 422
    factory.dispose()


def test_run_operations_are_filterable_through_the_owning_project_contract(tmp_path):
    client, factory, project, automation, _ = client_for(tmp_path)
    key = str(uuid4())
    response = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": key},
        json=start_payload(automation),
    )
    assert response.status_code == 202
    found = client.get(
        f"/api/v1/projects/{project.project_id}/operations/by-idempotency-key/{key}"
    )
    assert found.status_code == 200
    assert found.json()["kind"] == "startBatch"
    assert (
        found.json()["result"]["batch"]["batchId"]
        == response.json()["operation"]["result"]["batch"]["batchId"]
    )

    other, _, _ = ProjectService(SqlAlchemyProjects(factory)).create(
        str(uuid4()), {"name": "其他运行项目", "description": ""}
    )
    for kind, expected_total in (
        ("startBatch", 1),
        ("stopBatch", 0),
        ("forceStopBatch", 0),
    ):
        filtered = client.get(
            f"/api/v1/projects/{project.project_id}/operations",
            params={"kind": kind, "resourceType": "batch"},
        )
        assert filtered.status_code == 200
        assert filtered.json()["total"] == expected_total
    other_project = client.get(
        f"/api/v1/projects/{other.project_id}/operations",
        params={"kind": "startBatch", "resourceType": "batch"},
    )
    assert other_project.status_code == 200
    assert other_project.json()["total"] == 0
    factory.dispose()


def test_task_directory_exposes_the_open_manual_item_and_never_invents_one(tmp_path):
    """PM5 的 002 画板要求等待人工的任务行能进入那份唯一的人工详情。"""
    client, factory, project, automation, _ = client_for(tmp_path)
    batch = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation, max_tasks=2),
    ).json()["operation"]["result"]["batch"]
    listed = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"]
    assert [item["manualItemId"] for item in listed] == [None, None]

    waiting = listed[0]
    now = datetime.now(UTC)
    manual_id = str(uuid4())
    with factory() as session:
        session.add(
            ProjectManualItemRow(
                id=manual_id,
                project_id=project.project_id,
                task_id=waiting["taskId"],
                run_id=waiting["runId"],
                instance_id=None,
                checkpoint_revision=1,
                status="waiting",
                status_revision=1,
                expires_at=None,
                allowed_targets=[],
                resume_started=False,
                reason="需要人工核对",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    refreshed = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"]
    by_task = {item["taskId"]: item["manualItemId"] for item in refreshed}
    assert by_task[waiting["taskId"]] == manual_id
    # 同批次其它任务不能被带上别人的人工事项
    assert [value for key, value in by_task.items() if key != waiting["taskId"]] == [None]

    # 已经结束的人工事项不再是入口，列表必须回到普通的任务跳转
    with factory() as session:
        row = session.get(ProjectManualItemRow, manual_id)
        assert row is not None
        row.status = "resolved"
        session.commit()
    resolved = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"]
    assert [item["manualItemId"] for item in resolved] == [None, None]
    factory.dispose()

def test_task_directory_reports_the_current_or_final_node_and_latest_status_time(tmp_path):
    """PM5 的 002 画板要求任务行给出「当前或结束节点」与「最近状态时间」。"""
    client, factory, project, automation, _ = client_for(tmp_path)
    batch = client.post(
        f"/api/v1/projects/{project.project_id}/automations/{automation.automation_id}/batches",
        headers={"Idempotency-Key": str(uuid4())},
        json=start_payload(automation),
    ).json()["operation"]["result"]["batch"]
    queued = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"][0]
    # 排队中的任务没有节点尝试，最近状态时间只能是任务创建时间，
    # 不能拿客户端时钟或排序字段伪造一个更新的时间。
    assert queued["endNodeName"] is None
    assert queued["lastStatusAt"] == queued["createdAt"]

    succeeded_at = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=3)
    with factory.begin() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        for index, status in enumerate(("started", "succeeded")):
            repository.append_event(
                {
                    "eventId": str(uuid4()),
                    "runId": queued["runId"],
                    "executionGeneration": 0,
                    "kind": "nodeAttempt",
                    "nodeId": "open",
                    "nodeVisitId": "visit-1",
                    "attempt": 1,
                    "occurredAt": (
                        succeeded_at - timedelta(seconds=1 - index)
                    ).isoformat(),
                    "payload": {"status": status},
                }
            )

    listed = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch["batchId"]},
    ).json()["items"][0]
    assert listed["endNodeName"] == "打开网页"
    assert datetime.fromisoformat(listed["lastStatusAt"]) == succeeded_at
    factory.dispose()
