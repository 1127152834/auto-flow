from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.project_runs import project_runs_router
from autoflow.adapters.http.projects import projects_router
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.projects.service import ProjectService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.project_run_models import ProjectBatchRow
from autoflow.infrastructure.database.project_runs import SqlAlchemyProjectRuns
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from tests.integration.test_project_run_start import setup, start_payload


class Scheduler:
    def __init__(self):
        self.wakes = 0

    def wake(self):
        self.wakes += 1


def client_for(tmp_path, resolver=None):
    factory, _, _, coordinator, _, project, automation = setup(tmp_path, resolver)
    scheduler = Scheduler()
    app = FastAPI()
    app.include_router(projects_router(ProjectService(SqlAlchemyProjects(factory))))
    app.include_router(
        project_runs_router(
            coordinator, ProjectRunQueries(factory), scheduler, QuiesceGate()
        )
    )
    return TestClient(app), factory, project, automation, scheduler


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
    assert detail["configurationSnapshot"]["automation"]["name"] == automation.name
    assert detail["configurationSnapshot"]["parameters"]["00000000-0000-0000-0000-000000000031"] == "每个任务的冻结值"
    assert detail["configurationSnapshot"]["parameters"]["00000000-0000-0000-0000-000000000032"] is False
    assert detail["configurationSnapshot"]["maxTasks"] == 2
    assert detail["configurationSnapshot"]["concurrency"] == 1
    assert detail["configurationSnapshot"]["workflowRevision"] == 1

    tasks = client.get(
        f"/api/v1/projects/{project.project_id}/tasks",
        params={"batchId": batch_id, "status": "queued", "pageSize": 1},
    ).json()
    assert tasks["total"] == 2 and len(tasks["items"]) == 1
    assert tasks["items"][0]["taskOrdinal"] in {1, 2}
    task_id = tasks["items"][0]["taskId"]
    task = client.get(f"/api/v1/projects/{project.project_id}/tasks/{task_id}").json()
    assert task["task"]["status"] == "queued"
    assert task["task"]["taskOrdinal"] == tasks["items"][0]["taskOrdinal"]
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


def test_batch_and_task_directories_search_persisted_identifiers_and_frozen_automation_name(tmp_path):
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

    assert by_name.status_code == 200 and by_name.json()["total"] == 1
    assert by_batch_id.status_code == 200 and by_batch_id.json()["total"] == 1
    assert by_task_id.status_code == 200 and by_task_id.json()["total"] == 1
    assert by_task_batch.status_code == 200 and by_task_batch.json()["total"] == 1
    assert client.get(
        f"/api/v1/projects/{project.project_id}/batches", params={"q": "不存在的自动化"}
    ).json()["total"] == 0
    assert client.get(
        f"/api/v1/projects/{project.project_id}/batches", params={"q": "x" * 121}
    ).status_code == 422
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
        assert tasks.json()["total"] == 0
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
