"""Remediation M3 R3-09 / R3-10: slim saves and reference-guarded generation cleanup."""

from uuid import uuid4

from autoflow.infrastructure.database.environments import _frozen_generations
from tests.contract.test_project_environments import _closed_instance, _project, make


def _save(client, project_id, instance_id, **body):
    response = client.post(
        f"/api/v1/projects/{project_id}/environment-saves",
        headers={"Idempotency-Key": str(uuid4())},
        json={"instanceId": instance_id, "expectedUseGeneration": 1, "executionGeneration": 1, **body},
    )
    assert response.status_code == 202, response.text
    return response.json()["outcome"]["saved"]


def _reserve(service, project_id, environment_id):
    return service.reserve(
        project_id,
        service.resolve(project_id, {"source": "fixedEnvironment", "environmentId": environment_id}),
        task_id=str(uuid4()), run_id=str(uuid4()), holder_kind="task", holder_id=str(uuid4()),
    )


def _update(client, service, project_id, environment_id, generation, marker: bytes):
    instance = _reserve(service, project_id, environment_id)
    (service.instance_path(instance.instance_id) / "Default" / "Cookies").write_bytes(marker)
    service.environments.set_instance_state(instance.instance_id, "closed")
    saved = _save(client, project_id, instance.instance_id, mode="update", expectedContentGeneration=generation)
    service.close_instance(project_id, instance.instance_id, environment_id)
    return saved["contentGeneration"]


def _environment(client, service, project_id):
    first = _closed_instance(service, project_id, b"v1")
    created = _save(client, project_id, first.instance_id, mode="saveAs", name="清理环境")
    service.close_instance(project_id, first.instance_id, None)
    return created["environmentId"]


def test_saves_leave_browser_caches_behind_unless_the_environment_keeps_them(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = _closed_instance(service, project_id, b"login")
    root = service.instance_path(instance.instance_id) / "Default"
    for cache in ("Cache/Cache_Data", "Code Cache/js", "GPUCache"):
        (root / cache).mkdir(parents=True)
        (root / cache / "blob").write_bytes(b"x" * 1024)
    (root / "Service Worker" / "ScriptCache").mkdir(parents=True)
    (root / "Service Worker" / "ScriptCache" / "sw").write_bytes(b"login-worker")
    created = _save(client, project_id, instance.instance_id, mode="saveAs", name="缓存环境")
    service.close_instance(project_id, instance.instance_id, None)
    environment_id = created["environmentId"]
    saved = service.store.generation_dir(environment_id, 1) / "Default"
    assert not (saved / "Cache").exists() and not (saved / "Code Cache").exists() and not (saved / "GPUCache").exists()
    assert (saved / "Service Worker" / "ScriptCache" / "sw").read_bytes() == b"login-worker"
    assert (saved / "Cookies").read_bytes() == b"login"

    patched = client.patch(
        f"/api/v1/projects/{project_id}/environments/{environment_id}",
        headers={"Idempotency-Key": str(uuid4())},
        json={"expectedMetadataRevision": 1, "keepBrowserCache": True},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["keepBrowserCache"] is True
    again = _reserve(service, project_id, environment_id)
    (service.instance_path(again.instance_id) / "Default" / "Cache").mkdir()
    (service.instance_path(again.instance_id) / "Default" / "Cache" / "blob").write_bytes(b"kept")
    service.environments.set_instance_state(again.instance_id, "closed")
    _save(client, project_id, again.instance_id, mode="update", expectedContentGeneration=1)
    assert (service.store.generation_dir(environment_id, 2) / "Default" / "Cache" / "blob").read_bytes() == b"kept"


def test_a_hundred_saves_keep_the_current_and_three_recent_generations(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    environment_id = _environment(client, service, project_id)
    generation = 1
    for index in range(100):
        generation = _update(client, service, project_id, environment_id, generation, f"v{index}".encode())
    assert service.store.generations(environment_id) == [generation - 3, generation - 2, generation - 1, generation]
    usage = client.get(f"/api/v1/projects/{project_id}/environments/{environment_id}/storage").json()
    single = usage["generations"][-1]["bytes"]
    assert usage["retainedBytes"] + usage["reclaimableBytes"] <= single * 4
    assert [row["keptFor"] for row in usage["generations"]] == ["history", "history", "history", "current"]


def test_a_task_frozen_on_an_old_generation_still_restores_it_after_a_hundred_saves(tmp_path):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    environment_id = _environment(client, service, project_id)
    # A reserved instance is a Task frozen on generation 1 that has not opened its browser yet.
    frozen = _reserve(service, project_id, environment_id)
    service.environments.set_instance_state(frozen.instance_id, "reserved")
    service.store.close_instance(frozen.instance_id)
    service.environments.release_occupancy(environment_id, frozen.instance_id)
    generation = 1
    for index in range(100):
        generation = _update(client, service, project_id, environment_id, generation, f"v{index}".encode())
    assert 1 in service.store.generations(environment_id)
    assert len(service.store.generations(environment_id)) == 5
    restored = service.store.restore_generation(environment_id, 1, frozen.instance_id)
    assert (restored / "Default" / "Cookies").read_bytes() == b"v1"
    usage = client.get(f"/api/v1/projects/{project_id}/environments/{environment_id}/storage").json()
    assert usage["generations"][0] == {"generation": 1, "bytes": usage["generations"][0]["bytes"], "keptFor": "instance"}


def test_frozen_requests_name_their_generation_anywhere_in_the_document():
    request = {"browser": "persistent", "nodeBrowserEnvironments": {"n1": {"environmentRef": {
        "projectId": "p", "environmentId": "e", "contentGeneration": 7, "metadataRevision": 2}}},
        "environmentRef": {"environmentId": "other", "contentGeneration": 3}}
    assert list(_frozen_generations(request, "e")) == [7]


def test_a_generation_that_cannot_be_moved_is_kept_for_the_next_save(tmp_path, monkeypatch):
    client, projects, service = make(tmp_path)
    project_id = _project(projects)
    environment_id = _environment(client, service, project_id)
    def busy(*_args):
        raise PermissionError("in use")
    monkeypatch.setattr(service.store, "trash_generation", busy)
    generation = 1
    for index in range(5):
        generation = _update(client, service, project_id, environment_id, generation, f"v{index}".encode())
    assert service.store.generations(environment_id) == [1, 2, 3, 4, 5, 6]
    monkeypatch.undo()
    _update(client, service, project_id, environment_id, generation, b"last")
    assert service.store.generations(environment_id) == [4, 5, 6, 7]
