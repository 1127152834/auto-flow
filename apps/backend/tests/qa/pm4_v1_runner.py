"""QA-only PM4 V1 runner over real management persistence and data capabilities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar, cast
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.workflows.dispatcher import UNKNOWN_RESULT_ERROR
from autoflow.domain.project_data.capabilities import (
    CreateProjectRecordCommand,
    SetRecordStatusCommand,
)
from autoflow.domain.project_data.identity import RecordKey, RecordKeyType
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.project_runs.models import batch_to_dict
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_data_models import (
    DataFieldRow,
    DataStatusRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectRecordLeaseRow,
    ProjectTaskInputSnapshotRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.project_runs import SqlAlchemyProjectRuns
from autoflow.infrastructure.database.projects import _json_dates
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowRunEventRow,
    WorkflowRunRow,
)

from .pm4_fake_executor import (
    CREATE_ACCOUNT,
    SET_EMAIL_STATUS,
    AcknowledgementLost,
    FakeExecutionRequest,
    FakeExecutionResult,
    PauseBarrier,
    PM4FakeExecutor,
    StepName,
)


@dataclass(frozen=True)
class PM4V1RunOutcome:
    result: FakeExecutionResult
    finalized: bool


@dataclass(frozen=True)
class _Claim:
    project_id: str
    batch_id: str
    task_id: str
    run_id: str
    execution_generation: int
    inputs: Mapping[str, Any]
    email_status_id: str
    account_table_id: str
    account_generation: str
    account_values: Mapping[str, Any]


class PM4V1FakeRunner:
    """Drive the approved three-table QA slice without invoking Studio or a browser."""

    boundary: ClassVar[dict[str, str]] = {
        "executor": "fake",
        "browser": "notExecuted",
        "studio": "notExecuted",
    }

    def __init__(
        self,
        factory: sessionmaker[Session],
        *,
        acknowledgement_loss_steps: Iterable[StepName] = (),
        pause_barrier: PauseBarrier | None = None,
        fail_step: StepName | None = None,
        simulate_crash_before_finalize: bool = False,
    ) -> None:
        self._factory = factory
        self._capabilities = ProjectDataCapabilityService(
            SqlAlchemyProjectDataCapabilities(factory)
        )
        self._ack_loss_steps = frozenset(acknowledgement_loss_steps)
        self._acknowledgements_lost: set[tuple[str, StepName]] = set()
        self._pause_barrier = pause_barrier
        self._fail_step = fail_step
        self._simulate_crash_before_finalize = simulate_crash_before_finalize

    async def tick(self) -> PM4V1RunOutcome | None:
        self._settle_stopping_batches()
        claim = self._claim_one()
        if claim is None:
            return None
        callbacks = _CapabilityCallbacks(self, claim)
        result = await PM4FakeExecutor(
            callbacks, pause_barrier=self._pause_barrier, fail_step=self._fail_step
        ).execute(
            FakeExecutionRequest(
                claim.task_id,
                claim.run_id,
                claim.execution_generation,
                claim.inputs,
            )
        )
        if self._simulate_crash_before_finalize:
            return PM4V1RunOutcome(result, False)
        return PM4V1RunOutcome(result, self._finalize(claim, result))

    def _settle_stopping_batches(self) -> None:
        """Finish QA-owned stop facts after the in-process fake executor is quiescent."""
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            batches = session.scalars(
                select(ProjectBatchRow)
                .where(ProjectBatchRow.status.in_(("stopping", "reconciling")))
                .order_by(ProjectBatchRow.created_at, ProjectBatchRow.id)
            ).all()
            if not batches:
                session.rollback()
                return
            now = datetime.now(UTC)
            for batch in batches:
                operations = session.scalars(
                    select(ProjectOperationRow).where(
                        ProjectOperationRow.project_id == batch.project_id,
                        ProjectOperationRow.kind.in_(("stopBatch", "forceStopBatch")),
                        ProjectOperationRow.status == "running",
                        ProjectOperationRow.resource["batchId"].as_string() == batch.id,
                    )
                ).all()
                force_requested = any(
                    operation.kind == "forceStopBatch" for operation in operations
                )
                tasks = session.scalars(
                    select(ProjectTaskRow).where(ProjectTaskRow.batch_id == batch.id)
                ).all()
                for task in tasks:
                    run = session.get(WorkflowRunRow, task.run_id)
                    if run is None or run.status in {
                        "succeeded",
                        "failed",
                        "cancelled",
                        "timed_out",
                        "interrupted",
                    }:
                        continue
                    if force_requested or run.status == "reconciling":
                        if run.status != "reconciling":
                            run.execution_generation += 1
                            run.status_revision += 1
                        run.status = "interrupted"
                        run.error = dict(UNKNOWN_RESULT_ERROR)
                    else:
                        if run.status != "stopping":
                            run.status_revision += 1
                        run.status = "cancelled"
                        run.error = None
                    run.status_revision += 1
                    run.updated_at = run.completed_at = now
                    run.last_sequence += 1
                    session.add(
                        _event(
                            run,
                            run.last_sequence,
                            "status",
                            {
                                "status": run.status,
                                "statusRevision": run.status_revision,
                            },
                            now,
                        )
                    )
                    for lease in session.scalars(
                        select(ProjectRecordLeaseRow).where(
                            ProjectRecordLeaseRow.task_id == task.id,
                            ProjectRecordLeaseRow.run_id == task.run_id,
                            ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
                        )
                    ):
                        lease.state = "released"
                        lease.updated_at = lease.released_at = now
                batch.status = "stopped"
                batch.status_revision += 1
                batch.completed_at = now
                session.flush()
                result = {
                    "batch": _json_dates(
                        batch_to_dict(
                            SqlAlchemyProjectRuns(session).batch(
                                batch.project_id, batch.id
                            )
                        )
                    )
                }
                for operation in operations:
                    operation.status = "succeeded"
                    operation.status_revision += 1
                    operation.result = result
                    operation.updated_at = operation.completed_at = now
            session.commit()

    def _claim_one(self) -> _Claim | None:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            rows = session.execute(
                select(
                    ProjectTaskRow,
                    ProjectTaskInputSnapshotRow,
                    WorkflowRunRow,
                    ProjectBatchRow,
                )
                .join(
                    ProjectTaskInputSnapshotRow,
                    ProjectTaskInputSnapshotRow.task_id == ProjectTaskRow.id,
                )
                .join(WorkflowRunRow, WorkflowRunRow.id == ProjectTaskRow.run_id)
                .join(ProjectBatchRow, ProjectBatchRow.id == ProjectTaskRow.batch_id)
                .where(
                    WorkflowRunRow.status.in_(("queued", "running")),
                    ProjectBatchRow.status.in_(("accepted", "running")),
                )
                .order_by(ProjectTaskRow.created_at, ProjectTaskRow.id)
            ).all()
            selected = next(
                (
                    row
                    for row in rows
                    if row[1].inputs
                    and any(
                        binding.get("capability") == "project.data"
                        for binding in row[2].capability_bindings
                        if isinstance(binding, dict)
                    )
                ),
                None,
            )
            if selected is None:
                session.rollback()
                return None
            task, snapshot, run, batch = selected
            claim = self._resolve_claim(session, task, snapshot, run)
            now = datetime.now(UTC)
            if run.status == "queued":
                run.status = "running"
                run.status_revision += 1
                run.execution_generation += 1
                run.started_at = now
                run.updated_at = now
                run.last_sequence += 1
                session.add(
                    _event(
                        run,
                        run.last_sequence,
                        "status",
                        {"status": "running", "statusRevision": run.status_revision},
                        now,
                    )
                )
                claim = _with_generation(claim, run.execution_generation)
            if batch.status != "running":
                batch.status = "running"
                batch.status_revision += 1
            session.commit()
            return claim

    def _resolve_claim(
        self,
        session: Session,
        task: ProjectTaskRow,
        snapshot: ProjectTaskInputSnapshotRow,
        run: WorkflowRunRow,
    ) -> _Claim:
        person, email = _required_roles(snapshot.inputs)
        email_ref = _record_ref(email["recordRef"])
        status = session.scalar(
            select(DataStatusRow).where(
                DataStatusRow.project_id == task.project_id,
                DataStatusRow.table_id == email_ref.table_id,
                DataStatusRow.name == "已使用",
                DataStatusRow.deleted.is_(False),
            )
        )
        account = session.scalar(
            select(DataTableRow).where(
                DataTableRow.project_id == task.project_id,
                DataTableRow.name == "账号",
                DataTableRow.published.is_(True),
            )
        )
        if status is None or account is None:
            raise ProjectError(
                "QA_FIXTURE_INCOMPLETE",
                "PM4 V1 requires the email status 已使用 and account table 账号",
                409,
            )
        fields = session.scalars(
            select(DataFieldRow)
            .where(
                DataFieldRow.project_id == task.project_id,
                DataFieldRow.table_id == account.id,
                DataFieldRow.dataset_generation == account.current_generation,
            )
            .order_by(DataFieldRow.position, DataFieldRow.id)
        ).all()
        values = _account_values(fields, person, email, task.id)
        return _Claim(
            task.project_id,
            task.batch_id,
            task.id,
            task.run_id,
            run.execution_generation,
            {"person": person, "email": email},
            status.id,
            account.id,
            account.current_generation,
            values,
        )

    def _finalize(self, claim: _Claim, result: FakeExecutionResult) -> bool:
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            run = session.get(WorkflowRunRow, claim.run_id)
            batch = session.get(ProjectBatchRow, claim.batch_id)
            if (
                run is None
                or batch is None
                or run.execution_generation != claim.execution_generation
                or run.status != "running"
                or batch.status != "running"
            ):
                session.rollback()
                return False
            now = datetime.now(UTC)
            run.last_sequence += 1
            session.add(
                _event(run, run.last_sequence, "output", {
                    "name": "测试执行边界",
                    "value": dict(self.boundary),
                }, now)
            )
            run.last_sequence += 1
            session.add(
                _event(run, run.last_sequence, "output", {
                    "name": "数据操作结果",
                    "value": _business_output(result),
                }, now)
            )
            run.status = "succeeded" if result.status == "succeeded" else "failed"
            run.status_revision += 1
            run.updated_at = run.completed_at = now
            run.error = dict(result.error) if result.error is not None else None
            run.last_sequence += 1
            session.add(
                _event(
                    run,
                    run.last_sequence,
                    "status",
                    {"status": run.status, "statusRevision": run.status_revision},
                    now,
                )
            )
            batch.status = "completed" if result.status == "succeeded" else "failed"
            batch.status_revision += 1
            batch.completed_at = now
            for lease in session.scalars(
                select(ProjectRecordLeaseRow).where(
                    ProjectRecordLeaseRow.task_id == claim.task_id,
                    ProjectRecordLeaseRow.run_id == claim.run_id,
                    ProjectRecordLeaseRow.state.in_(("held", "reconciling")),
                )
            ):
                lease.state = "released"
                lease.updated_at = lease.released_at = now
            session.commit()
            return True

    def _lose_acknowledgement(self, task_id: str, step: StepName) -> bool:
        key = (task_id, step)
        if step not in self._ack_loss_steps or key in self._acknowledgements_lost:
            return False
        self._acknowledgements_lost.add(key)
        return True

    def _assert_execution_active(self, claim: _Claim) -> None:
        with self._factory() as session:
            run = session.get(WorkflowRunRow, claim.run_id)
            batch = session.get(ProjectBatchRow, claim.batch_id)
            if (
                run is None
                or batch is None
                or run.status != "running"
                or batch.status != "running"
            ):
                raise ProjectError(
                    "LEASE_REVOKED",
                    "PM4 V1 fake execution no longer owns the active generation",
                    409,
                )


class _CapabilityCallbacks:
    def __init__(self, runner: PM4V1FakeRunner, claim: _Claim) -> None:
        self._runner = runner
        self._claim = claim
        self._scope = runner._capabilities.scope(
            claim.project_id,
            claim.task_id,
            claim.run_id,
        )

    def set_status(self, **arguments):
        self._runner._assert_execution_active(self._claim)
        email = arguments["email"]
        result, _replayed = self._runner._capabilities.set_record_status(
            self._scope,
            SetRecordStatusCommand(
                arguments["operation_id"],
                arguments["execution_generation"],
                _record_ref(email["recordRef"]),
                self._claim.email_status_id,
                email["statusRevision"],
            ),
        )
        if self._runner._lose_acknowledgement(
            self._claim.task_id, SET_EMAIL_STATUS
        ):
            raise AcknowledgementLost
        return result

    def create_record(self, **arguments):
        self._runner._assert_execution_active(self._claim)
        result, _replayed = self._runner._capabilities.create_record(
            self._scope,
            CreateProjectRecordCommand(
                arguments["operation_id"],
                arguments["execution_generation"],
                self._claim.project_id,
                self._claim.account_table_id,
                self._claim.account_generation,
                self._claim.account_values,
            ),
        )
        if self._runner._lose_acknowledgement(self._claim.task_id, CREATE_ACCOUNT):
            raise AcknowledgementLost
        return result

    def query_operation(self, **arguments):
        return self._runner._capabilities.query_operation(
            self._scope, arguments["operation_id"]
        )


def _business_output(result: FakeExecutionResult) -> dict[str, str]:
    summary: dict[str, str] = {}
    if "emailStatus" in result.outputs:
        summary["邮箱状态"] = "已使用"
    if "account" in result.outputs:
        summary["账号记录"] = "已新增 1 条"
    if not summary:
        summary["执行结果"] = "未完成数据写入"
    return summary


def _required_roles(inputs: list[dict[str, Any]]) -> tuple[dict, dict]:
    if len(inputs) != 2:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE",
            "PM4 V1 fake execution requires exactly two frozen inputs",
            409,
        )
    person = next((item for item in inputs if _matches(item, "人员", "person")), None)
    email = next((item for item in inputs if _matches(item, "邮箱", "email")), None)
    if person is None or email is None or person is email:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE",
            "PM4 V1 inputs must identify person and email roles",
            409,
        )
    return person, email


def _matches(value: Mapping[str, Any], chinese: str, english: str) -> bool:
    labels = " ".join(
        str(value.get(key, "")) for key in ("alias", "tableDisplay", "name")
    ).casefold()
    return chinese in labels or english in labels


def _account_values(
    fields: Sequence[DataFieldRow],
    person: Mapping[str, Any],
    email: Mapping[str, Any],
    task_id: str,
) -> dict[str, Any]:
    person_value, email_value = _primary_value(person), _primary_value(email)
    values: dict[str, Any] = {}
    for field in fields:
        if not field.writable or field.formula:
            continue
        label = f"{field.key} {field.name}".casefold()
        if "人员" in label or "person" in label:
            value = person_value
        elif "邮箱" in label or "email" in label:
            value = email_value
        else:
            value = f"PM4-FAKE-{task_id[:8]}"
        if field.required or any(
            token in label for token in ("人员", "person", "邮箱", "email", "结果", "result")
        ):
            values[field.id] = value
    return values


def _primary_value(value: Mapping[str, Any]) -> Any:
    fields = value.get("values")
    if not isinstance(fields, list | tuple) or not fields:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE", "Frozen input has no business value", 409
        )
    first = fields[0]
    if not isinstance(first, Mapping) or "value" not in first:
        raise ProjectError(
            "QA_FIXTURE_INCOMPLETE", "Frozen input value is malformed", 409
        )
    return first["value"]


def _record_ref(value: Mapping[str, Any]) -> RecordRef:
    key = value["recordKey"]
    return RecordRef(
        str(value["projectId"]),
        str(value["tableId"]),
        str(value["datasetGeneration"]),
        RecordKey(cast(RecordKeyType, str(key["type"])), key["value"]),
    )


def _with_generation(claim: _Claim, generation: int) -> _Claim:
    return _Claim(
        claim.project_id,
        claim.batch_id,
        claim.task_id,
        claim.run_id,
        generation,
        claim.inputs,
        claim.email_status_id,
        claim.account_table_id,
        claim.account_generation,
        claim.account_values,
    )


def _event(
    run: WorkflowRunRow,
    sequence: int,
    kind: str,
    payload: dict[str, Any],
    occurred_at: datetime,
) -> WorkflowRunEventRow:
    event_id = str(
        uuid5(
            NAMESPACE_URL,
            f"autoflow:pm4-v1:{run.id}:{run.execution_generation}:{sequence}:{kind}",
        )
    )
    return WorkflowRunEventRow(
        run_id=run.id,
        sequence=sequence,
        event_id=event_id,
        execution_generation=run.execution_generation,
        kind=kind,
        node_id=None,
        node_visit_id=None,
        attempt=None,
        occurred_at=occurred_at,
        payload=payload,
    )
