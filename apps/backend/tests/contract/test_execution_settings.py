"""Remediation M1 R1-07 / AC1-06: the saved limit is what the dispatcher and workers use."""

from fastapi.testclient import TestClient


def put(client: TestClient, value, revision):
    return client.put(
        "/api/v1/settings/execution", json={"maxRunningBrowsers": value, "expectedRevision": revision}
    )


def test_get_reports_the_recommendation_that_the_dispatcher_runs_with(client: TestClient):
    body = client.get("/api/v1/settings/execution").json()
    dispatcher = client.app.state.project_workflow_dispatcher
    assert body["revision"] == 0
    assert body["maxRunningBrowsers"] is None
    assert body["effectiveMaxRunningBrowsers"] == body["recommendedMaxRunningBrowsers"] == dispatcher.capacity
    assert body["maxLiveBrowsers"] == dispatcher.live_capacity == 2 * dispatcher.capacity
    assert set(body["hardware"]) == {"logicalCpus", "totalMemoryGb"}
    assert isinstance(body["memoryPressure"], bool)


def test_put_applies_to_the_dispatcher_and_worker_manager_and_survives_restart_values(client: TestClient):
    saved = put(client, 7, 0)
    assert saved.status_code == 200
    body = saved.json()
    assert (body["maxRunningBrowsers"], body["effectiveMaxRunningBrowsers"], body["maxLiveBrowsers"], body["revision"]) == (7, 7, 14, 1)
    dispatcher = client.app.state.project_workflow_dispatcher
    worker = client.app.state.project_workflow_worker_manager
    assert (dispatcher.capacity, dispatcher.live_capacity, worker._capacity) == (7, 14, 14)
    assert client.get("/api/v1/settings/execution").json() == body

    lowered = put(client, 2, 1).json()
    assert (lowered["revision"], dispatcher.capacity, dispatcher.live_capacity) == (2, 2, 4)

    restored = put(client, None, 2).json()
    assert restored["maxRunningBrowsers"] is None
    assert restored["effectiveMaxRunningBrowsers"] == restored["recommendedMaxRunningBrowsers"] == dispatcher.capacity


def test_stale_revision_is_a_409_with_the_current_revision(client: TestClient):
    assert put(client, 3, 0).status_code == 200
    stale = put(client, 4, 0)
    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "SETTINGS_REVISION_CONFLICT"
    assert error["details"] == {"currentRevision": 1}
    assert client.get("/api/v1/settings/execution").json()["maxRunningBrowsers"] == 3


def test_invalid_values_are_422_and_change_nothing(client: TestClient):
    dispatcher = client.app.state.project_workflow_dispatcher
    before = dispatcher.capacity
    for value in (0, 65, "3", True, 2.5):
        assert put(client, value, 0).status_code == 422, value
    assert client.put("/api/v1/settings/execution", json={"maxRunningBrowsers": 3}).status_code == 422
    assert client.put("/api/v1/settings/execution", json={"maxRunningBrowsers": 3, "expectedRevision": "0"}).status_code == 422
    assert client.put("/api/v1/settings/execution", json={"maxRunningBrowsers": 3, "expectedRevision": -1}).status_code == 422
    assert dispatcher.capacity == before
    assert client.get("/api/v1/settings/execution").json()["revision"] == 0
