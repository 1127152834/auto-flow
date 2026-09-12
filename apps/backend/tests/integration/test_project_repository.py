from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import Base, ProjectRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects


def service_for(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return ProjectService(SqlAlchemyProjects(factory)), engine


def test_projects_and_operation_snapshots_survive_restart(tmp_path):
    path = tmp_path / "projects.sqlite3"
    service, engine = service_for(path)
    project, _operation, _ = service.create(
        "00000000-0000-0000-0000-000000000001", {"name": "Alpha", "description": "one"}
    )
    service.update(
        project.project_id,
        "00000000-0000-0000-0000-000000000002",
        {"description": "two", "expectedManagementRevision": 1},
    )
    replayed, _, replay = service.create(
        "00000000-0000-0000-0000-000000000001",
        {"name": "Alpha", "description": "one"},
    )
    assert replay is True
    assert replayed.description == "one" and replayed.management_revision == 1
    engine.dispose()
    reopened, engine = service_for(path)
    assert reopened.get(project.project_id).description == "two"
    assert (
        reopened.workspace_operation("00000000-0000-0000-0000-000000000001").result[
            "description"
        ]
        == "one"
    )
    engine.dispose()


def test_same_key_replays_and_different_payload_conflicts(tmp_path):
    service, engine = service_for(tmp_path / "p.sqlite3")
    key = "00000000-0000-0000-0000-000000000001"
    first = service.create(key, {"name": "Alpha", "description": ""})
    second = service.create(key, {"name": "Alpha", "description": ""})
    assert second[2] is True and second[0] == first[0]
    with pytest.raises(ProjectError) as caught:
        service.create(key, {"name": "Beta", "description": ""})
    assert caught.value.code == "OPERATION_PAYLOAD_MISMATCH"
    engine.dispose()


def test_noop_update_keeps_revision_but_records_operation(tmp_path):
    service, engine = service_for(tmp_path / "noop.sqlite3")
    project, _, _ = service.create(
        "00000000-0000-0000-0000-000000000001",
        {"name": "Alpha", "description": "same"},
    )
    saved, operation = service.update(
        project.project_id,
        "00000000-0000-0000-0000-000000000002",
        {"description": "same", "expectedManagementRevision": 1},
    )
    assert saved.management_revision == 1
    assert operation.result["managementRevision"] == 1
    assert operation.created_at <= operation.completed_at
    assert operation.resource == {"type": "project", "projectId": project.project_id}
    engine.dispose()


@pytest.mark.parametrize(
    ("state", "edit_code", "edit_status", "open_status"),
    [
        ("closing", "PROJECT_CLOSING", 423, None),
        ("archived", "LIFECYCLE_CONFLICT", 409, None),
        ("deleting", "LIFECYCLE_CONFLICT", 409, "LIFECYCLE_CONFLICT"),
        ("deleted", "PROJECT_NOT_FOUND", 404, "PROJECT_NOT_FOUND"),
    ],
)
def test_lifecycle_controls_reads_edits_and_open(
    tmp_path, state, edit_code, edit_status, open_status
):
    service, engine = service_for(tmp_path / f"{state}.sqlite3")
    project, _, _ = service.create(
        "00000000-0000-0000-0000-000000000001",
        {"name": "Alpha", "description": ""},
    )
    with sessionmaker(bind=engine)() as session:
        row = session.get(ProjectRow, project.project_id)
        row.lifecycle_state = state
        session.commit()
    if state == "deleting":
        assert service.get(project.project_id).lifecycle_state == "deleting"
    elif state == "deleted":
        with pytest.raises(ProjectError):
            service.get(project.project_id)
    with pytest.raises(ProjectError) as edit:
        service.update(
            project.project_id,
            "00000000-0000-0000-0000-000000000002",
            {"name": "Beta", "expectedManagementRevision": 1},
        )
    assert (edit.value.code, edit.value.status) == (edit_code, edit_status)
    if open_status:
        with pytest.raises(ProjectError) as opened:
            service.open(project.project_id)
        assert opened.value.code == open_status
    else:
        assert service.open(project.project_id).last_opened_at is not None
    engine.dispose()


def test_competing_casefolded_names_have_one_winner(tmp_path):
    service, engine = service_for(tmp_path / "p.sqlite3")
    barrier = Barrier(2)

    def create(args):
        barrier.wait()
        try:
            return service.create(args[0], {"name": args[1], "description": ""})
        except ProjectError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                create,
                [
                    ("00000000-0000-0000-0000-000000000001", "Alpha"),
                    ("00000000-0000-0000-0000-000000000002", "ALPHA"),
                ],
            )
        )
    assert (
        sum(
            isinstance(x, ProjectError) and x.code == "PROJECT_NAME_CONFLICT"
            for x in results
        )
        == 1
    )
    assert service.list()[1] == 1
    winner = next(item for item in results if not isinstance(item, ProjectError))[0]
    assert len(service.projects.list_operations(winner.project_id)[0]) == 1
    engine.dispose()


def test_search_treats_like_metacharacters_as_literal(tmp_path):
    service, engine = service_for(tmp_path / "search.sqlite3")
    service.create(
        "00000000-0000-0000-0000-000000000001",
        {"name": "100%", "description": "under_score"},
    )
    service.create(
        "00000000-0000-0000-0000-000000000002",
        {"name": "plain", "description": "ordinary"},
    )
    assert service.list(q="%", page=1, page_size=50, sort="name")[1] == 1
    assert service.list(q="_", page=1, page_size=50, sort="name")[1] == 1
    engine.dispose()


def test_competing_updates_have_one_cas_winner(tmp_path):
    service, engine = service_for(tmp_path / "cas.sqlite3")
    project, _, _ = service.create(
        "00000000-0000-0000-0000-000000000001", {"name": "Alpha", "description": ""}
    )
    barrier = Barrier(2)

    def update_project(args):
        barrier.wait()
        try:
            return service.update(
                project.project_id,
                args[0],
                {"description": args[1], "expectedManagementRevision": 1},
            )
        except ProjectError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                update_project,
                [
                    ("00000000-0000-0000-0000-000000000002", "a"),
                    ("00000000-0000-0000-0000-000000000003", "b"),
                ],
            )
        )
    assert (
        sum(
            isinstance(item, ProjectError) and item.code == "REVISION_CONFLICT"
            for item in results
        )
        == 1
    )
    assert service.get(project.project_id).management_revision == 2
    engine.dispose()


def test_last_opened_time_survives_restart(tmp_path):
    path = tmp_path / "opened.sqlite3"
    service, engine = service_for(path)
    project, _, _ = service.create(
        "00000000-0000-0000-0000-000000000001", {"name": "Alpha", "description": ""}
    )
    opened = service.open(project.project_id)
    engine.dispose()
    reopened, engine = service_for(path)
    assert reopened.get(project.project_id).last_opened_at == opened.last_opened_at
    engine.dispose()
