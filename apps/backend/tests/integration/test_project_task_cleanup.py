"""PM8-B2: the task detail's cleanup residue is a real, verifiable fact.

The prototype set treats three confirmations as independent: the run outcome,
the environment cleanup and the record occupancy.  These cases pin that the
projection reads durable rows instead of deriving one from another, and that
an unconfirmed cleanup can never be rendered as success.
"""

from datetime import UTC, datetime

from autoflow.adapters.http.project_run_schemas import TaskDetail
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
)
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_data_start import uid
from tests.integration.test_project_run_evidence import _claim

BROWSER_REQUEST = {
    "browser": "newFromProfile",
    "profileId": "profile-1",
    "kernelId": "public:1",
    "proxy": {"mode": "none"},
    "modelProviderId": None,
}


def _cleanup_of(factory, project_id, task_id):
    detail = ProjectRunQueries(factory).task_detail(project_id, task_id)
    TaskDetail.model_validate(detail)
    return detail["cleanup"]


def _use_browser(factory, run_id):
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, run_id)
        assert run is not None
        run.resource_request = dict(BROWSER_REQUEST)


def _work_copy(factory, project_id, task, state):
    with factory.begin() as session:
        now = datetime.now(UTC)
        session.add(
            ProjectEnvironmentInstanceRow(
                id=uid(),
                project_id=project_id,
                environment_id=None,
                state=state,
                source="task",
                source_content_generation=None,
                instance_use_generation=1,
                active_task_id=task.task_id,
                active_run_id=task.run_id,
                maintenance_operation_id=None,
                profile_id=uid(),
                identity_package={},
                created_at=now,
                updated_at=now,
            )
        )


def test_a_run_without_a_browser_reports_cleanup_not_required(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)

    assert _cleanup_of(factory, project_id, task.task_id) == {
        "status": "notRequired",
        "operationId": None,
        "message": None,
    }


def test_a_browser_run_that_has_not_finished_reports_cleanup_pending(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)

    cleanup = _cleanup_of(factory, project_id, task.task_id)

    assert cleanup["status"] == "pending"
    assert cleanup["operationId"] is None
    assert "任务结束后" in cleanup["message"]


def test_a_finished_browser_run_reports_cleanup_succeeded(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "succeeded"
        run.status_revision += 1
        run.completed_at = datetime.now(UTC)

    assert _cleanup_of(factory, project_id, task.task_id)["status"] == "succeeded"


def test_an_unconfirmed_cleanup_never_borrows_the_run_outcome(tmp_path):
    """A run that reached success is still unverified residue for cleanup."""
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "reconciling"
        run.status_revision += 1
        run.completed_at = datetime.now(UTC)

    cleanup = _cleanup_of(factory, project_id, task.task_id)

    assert cleanup["status"] == "unknown"
    assert "核验" in cleanup["message"]


def test_a_failed_work_copy_cleanup_is_visible_with_its_residue(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)
    _work_copy(factory, project_id, task, "cleanup_failed")

    cleanup = _cleanup_of(factory, project_id, task.task_id)

    assert cleanup["status"] == "failed"
    assert "残留" in cleanup["message"]


def test_a_closed_work_copy_is_reported_as_still_cleaning(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)
    _work_copy(factory, project_id, task, "closed")

    assert _cleanup_of(factory, project_id, task.task_id)["status"] == "running"


def test_a_live_work_copy_is_pending_not_cleaned(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)
    _work_copy(factory, project_id, task, "active")

    assert _cleanup_of(factory, project_id, task.task_id)["status"] == "pending"


def test_a_removed_work_copy_reports_cleanup_succeeded(tmp_path):
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)
    _work_copy(factory, project_id, task, "cleaned")

    assert _cleanup_of(factory, project_id, task.task_id)["status"] == "succeeded"


def test_cleanup_ignores_record_occupancy_that_is_still_held(tmp_path):
    """Data occupancy is a separate confirmation and never feeds cleanup."""
    factory, project_id, _coordinator, task = _claim(tmp_path)
    _use_browser(factory, task.run_id)
    with factory.begin() as session:
        leases = session.query(ProjectRecordLeaseRow).filter_by(task_id=task.task_id)
        assert leases.count() == 2
        for lease in leases:
            lease.state = "reconciling"
        run = session.get(WorkflowRunRow, task.run_id)
        run.status = "succeeded"
        run.status_revision += 1
        run.completed_at = datetime.now(UTC)

    assert _cleanup_of(factory, project_id, task.task_id)["status"] == "succeeded"
