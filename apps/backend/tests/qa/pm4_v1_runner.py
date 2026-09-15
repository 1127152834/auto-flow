"""QA-only PM4 V1 runner over real management persistence and data capabilities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal, cast
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.workflows.dispatcher import UNKNOWN_RESULT_ERROR
from autoflow.domain.project_data.capabilities import (
    AddProjectFieldCommand,
    CreateProjectRecordCommand,
    DeleteProjectRecordCommand,
    EnsureProjectFieldCommand,
    ModifyProjectFieldCommand,
    PreviewProjectFieldChangeRequest,
    QueryProjectRecordsRequest,
    ReadProjectRecordRequest,
    SetRecordStatusCommand,
    UpdateProjectRecordCommand,
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
    ADD_ACCOUNT_FIELD,
    CREATE_ACCOUNT,
    SET_EMAIL_STATUS,
    AcknowledgementLost,
    FakeExecutionRequest,
    FakeExecutionResult,
    PauseBarrier,
    PM4FakeExecutor,
    StepName,
    stable_operation_id,
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
        mode: Literal["v1", "b"] = "v1",
        max_auto_tasks: int | None = None,
    ) -> None:
        if max_auto_tasks is not None and max_auto_tasks < 1:
            raise ValueError("max_auto_tasks must be positive")
        self._factory = factory
        self._capabilities = ProjectDataCapabilityService(
            SqlAlchemyProjectDataCapabilities(factory)
        )
        self._ack_loss_steps = frozenset(acknowledgement_loss_steps)
        self._acknowledgements_lost: set[tuple[str, StepName]] = set()
        self._pause_barrier = pause_barrier
        self._fail_step = fail_step
        self._simulate_crash_before_finalize = simulate_crash_before_finalize
        self._mode = mode
        self._max_auto_tasks = max_auto_tasks
        self._finalized_tasks = 0

    async def tick(self) -> PM4V1RunOutcome | None:
        self._settle_stopping_batches()
        if (
            self._max_auto_tasks is not None
            and self._finalized_tasks >= self._max_auto_tasks
        ):
            return None
        claim = self._claim_one()
        if claim is None:
            pending = self._pending_data_batch()
            if pending is not None:
                claim_outcome = ProjectBatchScheduler.claim_data_task(
                    self._factory, pending[0], pending[1]
                )
                if claim_outcome != "ready":
                    self._settle_claim_outcome(pending[0], pending[1], claim_outcome)
                claim = self._claim_one()
        if claim is None:
            return None
        callbacks = _CapabilityCallbacks(self, claim)
        result = await PM4FakeExecutor(
            callbacks,
            pause_barrier=self._pause_barrier,
            fail_step=self._fail_step,
            mode=self._mode,
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
        finalized = self._finalize(claim, result)
        if finalized:
            self._finalized_tasks += 1
        return PM4V1RunOutcome(result, finalized)

    def _settle_claim_outcome(
        self, project_id: str, batch_id: str, claim_outcome: str
    ) -> None:
        """Project the real scheduler's idle outcome for the QA-owned executor."""
        status = {
            "temporarilyBusy": "blocked",
            "scanBudgetExceeded": "blocked",
            "configurationError": "failed",
            "ambiguous": "failed",
            "noMatch": "completed",
        }.get(claim_outcome)
        if status is None:
            return
        with self._factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            batch = session.get(ProjectBatchRow, batch_id)
            if batch is None or batch.project_id != project_id:
                session.rollback()
                return
            now = datetime.now(UTC)
            if batch.status != status:
                batch.status = status
                batch.status_revision += 1
            if status in {"completed", "failed"}:
                batch.completed_at = now
            session.commit()

    def _pending_data_batch(self) -> tuple[str, str] | None:
        with self._factory() as session:
            return session.execute(
                select(ProjectBatchRow.project_id, ProjectBatchRow.id)
                .where(
                    ProjectBatchRow.claim_gate_state == "open",
                    ProjectBatchRow.status.in_(("accepted", "blocked", "running")),
                )
                .order_by(ProjectBatchRow.created_at, ProjectBatchRow.id)
                .limit(1)
            ).one_or_none()

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
                _event(
                    run,
                    run.last_sequence,
                    "output",
                    {
                        "name": "测试执行边界",
                        "value": dict(self.boundary),
                    },
                    now,
                )
            )
            run.last_sequence += 1
            session.add(
                _event(
                    run,
                    run.last_sequence,
                    "output",
                    {
                        "name": "数据操作结果",
                        "value": _business_output(result),
                    },
                    now,
                )
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
            task_count = session.scalar(
                select(func.count())
                .select_from(ProjectTaskRow)
                .where(ProjectTaskRow.batch_id == claim.batch_id)
            )
            target = batch.frozen_request.get("maxTasks")
            continue_after_failure = bool(
                batch.frozen_request["automation"]["runPolicy"].get(
                    "continueAfterFailure", False
                )
            )
            if result.status == "failed" and not continue_after_failure:
                next_batch_status = "failed"
                batch.claim_gate_state = "closed"
                batch.completed_at = now
            elif target is not None and int(task_count or 0) >= int(target):
                next_batch_status = "completed"
                batch.claim_gate_state = "closed"
                batch.selection_outcome = {"status": "limitReached"}
                batch.completed_at = now
            else:
                next_batch_status = "running"
                batch.completed_at = None
            if batch.status != next_batch_status:
                batch.status = next_batch_status
                batch.status_revision += 1
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
        self._email_after_clear: dict[str, Any] | None = None
        self._account: dict[str, Any] | None = None
        self._account_read: dict[str, Any] | None = None
        self._disposable: dict[str, Any] | None = None
        self._disposable_read: dict[str, Any] | None = None
        self._added_field: dict[str, Any] | None = None
        self._ensured_field: dict[str, Any] | None = None

    def read_person(self, **arguments):
        person = arguments["person"]
        return self._runner._capabilities.read_record(
            self._scope,
            ReadProjectRecordRequest(
                arguments["execution_generation"],
                _record_ref(person["recordRef"]),
                [item["fieldId"] for item in person["values"]],
                "workflow",
            ),
        )

    def clear_status(self, **arguments):
        self._runner._assert_execution_active(self._claim)
        email = arguments["email"]
        self._email_after_clear, _replayed = (
            self._runner._capabilities.set_record_status(
                self._scope,
                SetRecordStatusCommand(
                    arguments["operation_id"],
                    arguments["execution_generation"],
                    _record_ref(email["recordRef"]),
                    None,
                    email["statusRevision"],
                ),
            )
        )
        return self._email_after_clear

    def set_status(self, **arguments):
        self._runner._assert_execution_active(self._claim)
        email = arguments["email"]
        expected_revision = (
            self._email_after_clear["statusRevision"]
            if self._email_after_clear is not None
            else email["statusRevision"]
        )
        result, _replayed = self._runner._capabilities.set_record_status(
            self._scope,
            SetRecordStatusCommand(
                arguments["operation_id"],
                arguments["execution_generation"],
                _record_ref(email["recordRef"]),
                self._claim.email_status_id,
                expected_revision,
            ),
        )
        if self._runner._lose_acknowledgement(self._claim.task_id, SET_EMAIL_STATUS):
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
        self._account = result
        return result

    def query_account(self, **arguments):
        result_field = self._field("result")
        result = self._runner._capabilities.query_records(
            self._scope,
            QueryProjectRecordsRequest(
                arguments["execution_generation"],
                self._claim.project_id,
                self._claim.account_table_id,
                self._claim.account_generation,
                self._field_ids(),
                "workflow",
                {
                    "type": "compare",
                    "fieldId": result_field.id,
                    "operator": "eq",
                    "value": self._claim.account_values[result_field.id],
                },
                [],
                None,
                10,
            ),
        )
        if len(result["items"]) != 1:
            raise ProjectError(
                "QA_FACT_MISMATCH", "PM4-B account query must return one record", 409
            )
        return result

    def read_account(self, **arguments):
        if self._account is None:
            raise ProjectError("QA_FACT_MISMATCH", "Account was not created", 409)
        self._account_read = self._runner._capabilities.read_record(
            self._scope,
            ReadProjectRecordRequest(
                arguments["execution_generation"],
                _record_ref(self._account["ref"]),
                self._field_ids(),
                "workflow",
            ),
        )
        return self._account_read

    def update_account(self, **arguments):
        if self._account_read is None:
            raise ProjectError("QA_FACT_MISMATCH", "Account was not read", 409)
        result_field = self._field("result")
        result, _replayed = self._runner._capabilities.update_record(
            self._scope,
            UpdateProjectRecordCommand(
                arguments["operation_id"],
                arguments["execution_generation"],
                _record_ref(self._account_read["ref"]),
                {result_field.id: "PM4-B-UPDATED"},
                self._account_read["contentRevision"],
            ),
        )
        self._account = result
        return result

    def create_disposable(self, **arguments):
        values = dict(self._claim.account_values)
        values[self._field("result").id] = "PM4-B-DISPOSABLE"
        self._disposable, _replayed = self._runner._capabilities.create_record(
            self._scope,
            CreateProjectRecordCommand(
                arguments["operation_id"],
                arguments["execution_generation"],
                self._claim.project_id,
                self._claim.account_table_id,
                self._claim.account_generation,
                values,
            ),
        )
        return self._disposable

    def read_disposable(self, **arguments):
        if self._disposable is None:
            raise ProjectError("QA_FACT_MISMATCH", "Disposable row is missing", 409)
        self._disposable_read = self._runner._capabilities.read_record(
            self._scope,
            ReadProjectRecordRequest(
                arguments["execution_generation"],
                _record_ref(self._disposable["ref"]),
                self._field_ids(),
                "workflow",
            ),
        )
        return self._disposable_read

    def delete_disposable(self, **arguments):
        if self._disposable_read is None:
            raise ProjectError("QA_FACT_MISMATCH", "Disposable row was not read", 409)
        result, _replayed = self._runner._capabilities.delete_record(
            self._scope,
            DeleteProjectRecordCommand(
                arguments["operation_id"],
                arguments["execution_generation"],
                _record_ref(self._disposable_read["ref"]),
                self._disposable_read["contentRevision"],
                self._disposable_read["statusRevision"],
                self._disposable_read["linkRevision"],
            ),
        )
        return result

    def add_account_field(self, **arguments):
        command = self._field_command(arguments, ensure=False)
        self._added_field, _replayed = self._runner._capabilities.add_field(
            self._scope, command
        )
        return self._added_field

    def ensure_account_field(self, **arguments):
        if self._added_field is None:
            raise ProjectError("QA_FACT_MISMATCH", "Field was not added", 409)
        command = self._field_command(
            arguments,
            ensure=True,
            table_revision=self._added_field["tableRevision"],
        )
        self._ensured_field, _replayed = self._runner._capabilities.ensure_field(
            self._scope, command
        )
        return self._ensured_field

    def modify_account_field(self, **arguments):
        if self._ensured_field is None:
            raise ProjectError("QA_FACT_MISMATCH", "Field was not ensured", 409)
        field = self._ensured_field["field"]
        definition = {
            "key": field["key"],
            "name": "执行备注",
            "type": field["type"],
            "required": field["required"],
            "validation": field["validation"],
        }
        preview = self._runner._capabilities.preview_field_change(
            self._scope,
            PreviewProjectFieldChangeRequest(
                arguments["execution_generation"],
                self._claim.project_id,
                self._claim.account_table_id,
                self._claim.account_generation,
                field["ref"]["fieldId"],
                definition,
            ),
        )
        result, _replayed = self._runner._capabilities.modify_field(
            self._scope,
            ModifyProjectFieldCommand(
                arguments["operation_id"],
                arguments["execution_generation"],
                self._claim.project_id,
                self._claim.account_table_id,
                self._claim.account_generation,
                field["ref"]["fieldId"],
                definition,
                self._ensured_field["tableRevision"],
                field["fieldRevision"],
                preview["impactRevision"],
            ),
        )
        return result

    def _field_ids(self) -> list[str]:
        with self._runner._factory() as session:
            return list(
                session.scalars(
                    select(DataFieldRow.id)
                    .where(
                        DataFieldRow.project_id == self._claim.project_id,
                        DataFieldRow.table_id == self._claim.account_table_id,
                        DataFieldRow.dataset_generation
                        == self._claim.account_generation,
                    )
                    .order_by(DataFieldRow.position, DataFieldRow.id)
                )
            )

    def _field(self, key: str) -> DataFieldRow:
        with self._runner._factory() as session:
            field = session.scalar(
                select(DataFieldRow).where(
                    DataFieldRow.project_id == self._claim.project_id,
                    DataFieldRow.table_id == self._claim.account_table_id,
                    DataFieldRow.dataset_generation == self._claim.account_generation,
                    DataFieldRow.key == key,
                )
            )
            if field is None:
                raise ProjectError("QA_FIXTURE_INCOMPLETE", f"Missing field {key}", 409)
            session.expunge(field)
            return field

    def _field_command(
        self,
        arguments: Mapping[str, Any],
        *,
        ensure: bool,
        table_revision: int | None = None,
    ) -> AddProjectFieldCommand | EnsureProjectFieldCommand:
        field_id = str(
            uuid5(
                NAMESPACE_URL,
                stable_operation_id(
                    self._claim.task_id,
                    self._claim.run_id,
                    arguments["execution_generation"],
                    ADD_ACCOUNT_FIELD,
                )
                + ":field",
            )
        )
        if table_revision is None:
            with self._runner._factory() as session:
                table = session.get(DataTableRow, self._claim.account_table_id)
                if table is None:
                    raise ProjectError(
                        "QA_FIXTURE_INCOMPLETE", "Account table missing", 409
                    )
                table_revision = table.table_revision
        values = (
            arguments["operation_id"],
            arguments["execution_generation"],
            self._claim.project_id,
            self._claim.account_table_id,
            self._claim.account_generation,
            field_id,
            {
                "key": "qa_note",
                "name": "QA 备注",
                "type": "string",
                "required": False,
                "validation": {},
            },
            False,
            None,
            table_revision,
        )
        return (
            EnsureProjectFieldCommand(*values)
            if ensure
            else AddProjectFieldCommand(*values)
        )

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
            token in label
            for token in ("人员", "person", "邮箱", "email", "结果", "result")
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
