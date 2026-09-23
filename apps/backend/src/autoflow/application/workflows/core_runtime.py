from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.models import WorkflowRepository, canonical_json
from autoflow.domain.workflows.run_validation import prepare_run as compile_workflow
from autoflow.domain.workflows.runtime import (
    CoreRun,
    CoreRunStatus,
    PreparedContent,
    WorkflowRuntimeError,
)
from autoflow.infrastructure.database.core_workflows import _record as workflow_record
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
    _is_sqlite_contention,
)


class CoreRunPort(Protocol):
    def prepare_run(
        self,
        *,
        run_request_id: str,
        prepared_content_id: str,
        parameters: dict[str, Any],
        input_snapshot_ref: dict[str, Any] | None,
        resource_request: dict[str, Any],
        capability_bindings: list[dict[str, Any]],
        uow: Session,
        created_at: datetime | None = None,
    ) -> CoreRun: ...

    def query_run(
        self, *, run_id: str | None = None, run_request_id: str | None = None
    ) -> CoreRun | None: ...

    def dispatch_run(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun: ...

    def cancel_run(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun: ...

    def force_stop(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun: ...


class WorkflowRuntimeService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        workflow_repository: WorkflowRepository | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._workflow_repository = workflow_repository

    def requires_browser(self, workflow_id: str) -> bool:
        from .runtime import WorkflowRuntime

        with self._session_factory() as session:
            row = session.get(WorkflowDocumentRow, workflow_id)
            # Missing documents are reported by document validation; resource
            # inspection must not silently treat them as a pure-data workflow.
            if row is None:
                return True
            return WorkflowRuntime(build_production_executor_registry()).requires_browser(
                workflow_record(row).document["content"]
            )

    def prepare_content(
        self,
        *,
        prepare_operation_id: str,
        workflow_id: str,
        source_revision: int,
        available_capabilities: list[str],
        created_at: datetime | None = None,
        uow: Session | None = None,
    ) -> PreparedContent:
        request_digest = _digest(
            {
                "kind": "prepareWorkflowContent",
                "workflowId": workflow_id,
                "sourceRevision": source_revision,
                "availableCapabilities": sorted(set(available_capabilities)),
            }
        )

        def prepare(session: Session) -> PreparedContent:
            return self._prepare_content_in_uow(
                session,
                prepare_operation_id=prepare_operation_id,
                workflow_id=workflow_id,
                source_revision=source_revision,
                available_capabilities=available_capabilities,
                request_digest=request_digest,
                created_at=created_at,
            )

        if uow is not None:
            return prepare(uow)
        with self._session_factory() as session:
            _begin_immediate_if_sqlite(session)
            content = prepare(session)
            session.commit()
            return content

    def _prepare_content_in_uow(
        self,
        session: Session,
        *,
        prepare_operation_id: str,
        workflow_id: str,
        source_revision: int,
        available_capabilities: list[str],
        request_digest: str,
        created_at: datetime | None,
    ) -> PreparedContent:
        runtime = SqlAlchemyWorkflowRuntimeRepository(session)
        existing = runtime.get_prepared_content(
            prepare_operation_id=prepare_operation_id
        )
        if existing is not None:
            if existing.request_digest != request_digest:
                raise WorkflowRuntimeError(
                    "OPERATION_PAYLOAD_MISMATCH",
                    "幂等键已用于另一准备请求",
                )
            return existing
        if self._workflow_repository is None:
            raise WorkflowRuntimeError(
                "WORKFLOW_RUNTIME_UNAVAILABLE", "工作流文档读取器尚未装配", 503
            )
        current = session.get(WorkflowDocumentRow, workflow_id)
        if current is None:
            raise WorkflowRuntimeError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
        if current.revision != source_revision:
            raise WorkflowRuntimeError(
                "WORKFLOW_REVISION_CONFLICT",
                "工作流已被修改",
                details={
                    "expectedRevision": source_revision,
                    "currentRevision": current.revision,
                },
            )
        record = workflow_record(current)
        prepared = compile_workflow(record.document)
        from .runtime import WorkflowRuntime

        requirements = (["browser.cloakbrowser"] if WorkflowRuntime(
            build_production_executor_registry()
        ).requires_browser(prepared.document["content"]) else [])
        missing = sorted(set(requirements) - set(available_capabilities))
        if missing:
            raise WorkflowRuntimeError(
                "CAPABILITY_MISSING",
                "当前服务缺少运行工作流所需的能力",
                422,
                details={"capabilities": missing},
            )
        execution_plan = _execution_plan(prepared.document, prepared.node_ids)
        adapter_version = "webrpa-graph/v1" if prepared.graph_adapter else "webrpa-chain/v1"
        if prepared.graph_adapter:
            execution_plan["document"] = prepared.document["content"]
        checksum = _digest(
            {
                "document": prepared.document,
                "executionPlan": execution_plan,
                "adapterVersion": adapter_version,
            }
        )
        content = runtime.prepare_content(
            prepared_content_id=str(uuid4()),
            prepare_operation_id=prepare_operation_id,
            request_digest=request_digest,
            workflow_id=workflow_id,
            source_revision=source_revision,
            checksum=checksum,
            document=prepared.document,
            execution_plan=execution_plan,
            adapter_version=adapter_version,
            capability_requirements=requirements,
            provenance={
                "kind": "workflowRevision",
                "revision": source_revision,
            },
            created_at=created_at or datetime.now(UTC),
        )
        return content

    def query_prepared_content(
        self,
        *,
        prepared_content_id: str | None = None,
        prepare_operation_id: str | None = None,
    ) -> PreparedContent | None:
        with self._session_factory() as session:
            return SqlAlchemyWorkflowRuntimeRepository(session).get_prepared_content(
                prepared_content_id=prepared_content_id,
                prepare_operation_id=prepare_operation_id,
            )

    def prepare_run(
        self,
        *,
        run_request_id: str,
        prepared_content_id: str,
        parameters: dict[str, Any],
        input_snapshot_ref: dict[str, Any] | None,
        resource_request: dict[str, Any],
        capability_bindings: list[dict[str, Any]],
        uow: Session,
        created_at: datetime | None = None,
    ) -> CoreRun:
        request_digest = _digest(
            {
                "kind": "prepareRun",
                "runRequestId": run_request_id,
                "preparedContentId": prepared_content_id,
                "parameters": parameters,
                "inputSnapshotRef": input_snapshot_ref,
                "resourceRequest": resource_request,
                "capabilityBindings": capability_bindings,
            }
        )
        return SqlAlchemyWorkflowRuntimeRepository(uow).prepare_run(
            run_id=str(uuid4()),
            run_request_id=run_request_id,
            request_digest=request_digest,
            prepared_content_id=prepared_content_id,
            parameters=parameters,
            input_snapshot_ref=input_snapshot_ref,
            resource_request=resource_request,
            capability_bindings=capability_bindings,
            created_at=created_at or datetime.now(UTC),
        )

    def query_run(
        self, *, run_id: str | None = None, run_request_id: str | None = None
    ) -> CoreRun | None:
        with self._session_factory() as session:
            return SqlAlchemyWorkflowRuntimeRepository(session).get_run(
                run_id=run_id, run_request_id=run_request_id
            )

    def dispatch_run(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
        return self._transition(
            run_id,
            target_status="running",
            expected_status_revision=expected_status_revision,
            execution_generation=execution_generation,
        )

    def cancel_run(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
        return self._transition(
            run_id,
            target_status="stopping",
            expected_status_revision=expected_status_revision,
            execution_generation=execution_generation,
        )

    def force_stop(
        self,
        run_id: str,
        *,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
        return self._transition(
            run_id,
            target_status="reconciling",
            expected_status_revision=expected_status_revision,
            execution_generation=execution_generation,
        )

    def _transition(
        self,
        run_id: str,
        *,
        target_status: CoreRunStatus,
        expected_status_revision: int,
        execution_generation: int,
    ) -> CoreRun:
        with self._session_factory() as session:
            changed = SqlAlchemyWorkflowRuntimeRepository(session).transition_run(
                run_id,
                target_status=target_status,
                expected_status_revision=expected_status_revision,
                expected_execution_generation=execution_generation,
                now=datetime.now(UTC),
            )
            session.commit()
            return changed


def _execution_plan(document: dict[str, Any], node_ids: list[str]) -> dict[str, Any]:
    nodes = {node["id"]: node for node in document["content"]["nodes"]}
    return {
        "orderedNodeIds": list(node_ids),
        "nodes": [
            {
                "nodeId": node_id,
                "moduleType": nodes[node_id]["data"]["moduleType"],
                "data": nodes[node_id]["data"],
            }
            for node_id in node_ids
        ],
    }


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _begin_immediate_if_sqlite(session: Session) -> None:
    connection = session.connection()
    if connection.dialect.name != "sqlite":
        return
    driver = getattr(connection.connection, "driver_connection", None)
    if driver is not None and not driver.in_transaction:
        try:
            session.execute(text("BEGIN IMMEDIATE"))
        except OperationalError as error:
            if not _is_sqlite_contention(error):
                raise
            raise WorkflowRuntimeError(
                "PREPARED_CONTENT_CONCURRENT_WRITE",
                "执行内容正在由另一请求准备",
            ) from error
