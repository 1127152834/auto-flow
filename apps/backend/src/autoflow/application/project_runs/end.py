"""Durable production End admission and recovery."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4, uuid5

from sqlalchemy import select, text

from autoflow.domain.environments.rules import validate_metadata
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.project_end import normalize_project_end
from autoflow.domain.workflows.variables import references_variable
from autoflow.infrastructure.database.environment_models import ProjectEndOperationRow
from autoflow.infrastructure.database.environments import _operation, _operation_row
from autoflow.infrastructure.database.models import ProjectOperationRow
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_run_models import (
    ProjectRecordLeaseRow,
    ProjectTaskRecordCursorRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runtime_models import (
    WorkflowPreparedContentRow,
    WorkflowRunEventRow,
    WorkflowRunRow,
)


def _end_configs(plan: Mapping[str, Any], node_id: str | None) -> list[dict[str, Any]]:
    documents = [plan.get("document", plan)]
    documents.extend(plan.get("workflowDependencies", {}).values())
    documents.extend(
        item.get("workflow", {})
        for item in plan.get("customModuleDependencies", {}).values()
        if isinstance(item, Mapping)
    )
    configs: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, Mapping):
            continue
        for node in document.get("nodes", ()):
            if not isinstance(node, Mapping):
                continue
            data = node.get("data", node)
            if (
                isinstance(data, Mapping)
                and (node_id is None or node.get("id", node.get("nodeId")) == node_id)
                and data.get("moduleType", node.get("moduleType")) == "project_end"
            ):
                raw = data.get("config", data)
                if isinstance(raw, Mapping):
                    configs.append(normalize_project_end(raw))
    return configs


def plan_retains_environment(plan: Mapping[str, Any]) -> bool:
    """True when any End in the frozen plan (sub-workflows included) keeps the login environment."""
    try:
        return any(config.get("retainEnvironment") for config in _end_configs(plan, None))
    except ValueError:
        return False  # an invalid End is rejected by its own run-time validation


class ProjectRunEnd:
    def __init__(self, sessions: Any, environments: Any) -> None:
        self.sessions = sessions
        self.environments = environments

    def accept(
        self, run_id: str, generation: int, request: dict[str, Any]
    ) -> dict[str, Any]:
        if (
            type(generation) is not int
            or generation < 1
            or set(request)
            != {
                "nodeId",
                "nodeVisitId",
                "attempt",
                "commandId",
                "operation",
                "arguments",
                "browserClosed",
            }
            or request.get("operation") != "end"
            or request.get("attempt") != 1
            or type(request.get("attempt")) is not int
            or request.get("browserClosed") is not True
        ):
            raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 请求无效", 403)
        node_id, visit = request.get("nodeId"), request.get("nodeVisitId")
        if (
            not isinstance(node_id, str)
            or not isinstance(visit, str)
            or request.get("commandId") != project_command_id(run_id, generation, visit)
        ):
            raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 命令身份无效", 403)
        args = request.get("arguments")
        if (
            not isinstance(args, dict)
            or not {"recordTargets"} <= set(args) <= {"recordTargets", "name", "businessResult"}
            or not isinstance(args["recordTargets"], list)
            or len(args["recordTargets"]) > 100
        ):
            raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 记录目标无效", 403)
        return self._accept(run_id, generation, request)

    def _accept(
        self, run_id: str, generation: int, request: dict[str, Any]
    ) -> dict[str, Any]:
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            task = session.scalar(
                select(ProjectTaskRow).where(ProjectTaskRow.run_id == run_id)
            )
            run = session.get(WorkflowRunRow, run_id)
            if task is None or run is None:
                raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 需要项目 Task", 403)
            if run.execution_generation != generation or run.status not in {
                "running",
                "finishing",
            }:
                raise ProjectError("LEASE_REVOKED", "End 执行授权已失效", 409)
            prepared = session.get(WorkflowPreparedContentRow, run.prepared_content_id)
            configs = (
                []
                if prepared is None
                else _end_configs(prepared.execution_plan, request["nodeId"])
            )
            visit = session.scalar(
                select(WorkflowRunEventRow)
                .where(
                    WorkflowRunEventRow.run_id == run_id,
                    WorkflowRunEventRow.execution_generation == generation,
                    WorkflowRunEventRow.node_id == request["nodeId"],
                    WorkflowRunEventRow.node_visit_id == request["nodeVisitId"],
                    WorkflowRunEventRow.attempt == 1,
                    WorkflowRunEventRow.kind == "nodeAttempt",
                )
                .order_by(WorkflowRunEventRow.sequence.desc())
                .limit(1)
            )
            if (
                not configs
                or any(config != configs[0] for config in configs)
                or visit is None
                or visit.payload.get("status") != "started"
            ):
                raise ProjectError(
                    "CAPABILITY_SCOPE_DENIED", "End 必须匹配冻结节点与已确认访问", 403
                )
            config = configs[0]
            existing = session.scalar(
                select(ProjectEndOperationRow).where(
                    ProjectEndOperationRow.run_id == run_id
                )
            )
            if existing is not None:
                operation = session.get(ProjectOperationRow, existing.operation_id)
                if (
                    operation is None
                    or existing.intended_result.get("workerRequest") != request
                ):
                    raise ProjectError(
                        "END_ALREADY_ACCEPTED", "本运行已接受另一结束意图", 409
                    )
                return {"endOperationId": operation.id, "phase": existing.phase}
            if run.status != "running":
                raise ProjectError("LEASE_REVOKED", "End 执行授权已失效", 409)
            frozen_name = config.get("name", "保留环境")
            name = request["arguments"].get("name", frozen_name)
            if type(name) is not str or (
                not references_variable(frozen_name) and name != frozen_name
            ):
                raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 名称必须匹配冻结配置", 403)
            name = validate_metadata(name=name)["name"]
            frozen_result = config.get("businessResult", "succeeded")
            business_result = request["arguments"].get("businessResult", frozen_result)
            if business_result not in {"succeeded", "failed"} or (
                frozen_result in {"succeeded", "failed"} and business_result != frozen_result
            ):
                raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 业务结果必须匹配冻结配置", 403)
            declared_targets = config.get("recordTargets", [])
            if isinstance(declared_targets, list):
                if request["arguments"]["recordTargets"] != declared_targets:
                    raise ProjectError(
                        "CAPABILITY_SCOPE_DENIED", "End 记录目标必须匹配冻结配置", 403
                    )
            elif not isinstance(declared_targets, str):
                raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 记录目标无效", 403)
            if not config.get("retainEnvironment") and request["arguments"]["recordTargets"]:
                raise ProjectError("CAPABILITY_SCOPE_DENIED", "End 未授权记录关联", 403)

            _task, _run, snapshot = SqlAlchemyProjectDataCapabilities._facts(
                session, task.project_id, task.id, run_id
            )
            binding = next(
                (
                    item
                    for item in run.capability_bindings
                    if item.get("capability") == "project.data"
                    and item.get("executionGeneration") == generation
                    and item.get("taskId") == task.id
                    and item.get("projectId") == task.project_id
                ),
                None,
            )
            if binding is None:
                raise ProjectError(
                    "CAPABILITY_SCOPE_DENIED", "End 缺少项目能力绑定", 403
                )
            wants_retain = config.get("retainEnvironment", False)
            if wants_retain and binding.get("executionMode") == "previewWrites":
                # R2-30: a preview never saves a login environment or links it to records.
                raise ProjectError(
                    "PREVIEW_CANNOT_SAVE_ENVIRONMENT", "预览运行不会保存登录状态，请用真实写入运行", 409
                )
            instance = self.environments.environments.find_instance_by_task(
                task.project_id, task.id
            )
            # Remediation M4 S8-4: a perIdentity task keeps its work copy for the identity's next task. The
            # login is saved once when the identity is released, and it belongs to the identity, so no
            # record is linked here.
            hold = (
                instance is not None
                and instance.identity_id is not None
                and (run.resource_request or {}).get("sessionMode") == "perIdentity"
            )
            targets: list[dict[str, Any]] = []
            if wants_retain and not hold:
                selected = config.get("inputIds")
                inputs = snapshot.inputs
                if selected is not None and set(selected) - {
                    item["inputId"] for item in inputs
                }:
                    raise ProjectError(
                        "CAPABILITY_SCOPE_DENIED", "End 输入目标不存在", 403
                    )
                writable_inputs = set(binding.get("statusInputIds", []))
                writable_inputs.update(
                    item["inputId"]
                    for item in inputs
                    if any(
                        grant.get("tableId") == item["recordRef"]["tableId"]
                        and grant.get("datasetGeneration")
                        == item["recordRef"]["datasetGeneration"]
                        and set(grant.get("operations", []))
                        & {"updateRecord", "setRecordStatus"}
                        for grant in binding.get("tableGrants", [])
                    )
                )
                refs = [
                    item["recordRef"]
                    for item in inputs
                    if item["inputId"] in writable_inputs
                    and (selected is None or item["inputId"] in selected)
                ]
                if selected is not None and set(selected) - writable_inputs:
                    raise ProjectError(
                        "CAPABILITY_SCOPE_DENIED",
                        "End 输入不具备本任务有效写入授权",
                        403,
                    )
                refs.extend(request["arguments"]["recordTargets"])
                for ref in refs:
                    if (
                        not isinstance(ref, dict)
                        or set(ref)
                        != {
                            "projectId",
                            "tableId",
                            "datasetGeneration",
                            "recordKey",
                        }
                        or ref["projectId"] != task.project_id
                    ):
                        raise ProjectError(
                            "CAPABILITY_SCOPE_DENIED", "End 记录作用域无效", 403
                        )
                    if any(target["recordRef"] == ref for target in targets):
                        continue
                    lease = session.scalar(
                        select(ProjectRecordLeaseRow).where(
                            ProjectRecordLeaseRow.task_id == task.id,
                            ProjectRecordLeaseRow.run_id == run_id,
                            ProjectRecordLeaseRow.project_id == task.project_id,
                            ProjectRecordLeaseRow.state == "held",
                            ProjectRecordLeaseRow.record_ref == ref,
                        )
                    )
                    cursor = (
                        None
                        if lease is None
                        else session.scalar(
                            select(ProjectTaskRecordCursorRow).where(
                                ProjectTaskRecordCursorRow.task_id == task.id,
                                ProjectTaskRecordCursorRow.lease_id == lease.id,
                            )
                        )
                    )
                    if cursor is None or (
                        cursor.source == "input"
                        and not any(
                            item["recordRef"] == ref
                            and item["inputId"] in writable_inputs
                            for item in inputs
                        )
                    ):
                        raise ProjectError(
                            "CAPABILITY_SCOPE_DENIED",
                            "End 记录不具备本任务有效写入占用",
                            403,
                        )
                    targets.append(
                        {
                            "recordRef": ref,
                            "expectedLinkRevision": cursor.link_revision,
                            "replaceAllowed": config.get("replaceAllowed", False),
                        }
                    )
            if wants_retain and (
                instance is None
                or instance.active_run_id != run_id
                or instance.state != "active"
            ):
                raise ProjectError(
                    "ENVIRONMENT_UNAVAILABLE", "End 没有可保留的任务环境", 409
                )
            if wants_retain and not hold:
                from autoflow.domain.environments.rules import bind_targets

                bind_targets(
                    instance.environment_id
                    if instance and config.get("saveMode", "auto") == "auto"
                    else "new-environment",
                    self.environments.environments.load_bind_targets(
                        task.project_id, targets
                    ),
                )
            retain = {
                "enabled": wants_retain,
                "recordTargets": targets,
                "mode": "update"
                if instance
                and instance.environment_id
                and config.get("saveMode", "auto") == "auto"
                else "save_as",
                "name": name,
                "expectedContentGeneration": instance.source_content_generation
                if instance
                else None,
            }
            payload = {
                "taskId": task.id,
                "runId": run_id,
                "instanceId": instance.instance_id if instance else None,
                "executionGeneration": generation,
                "expectedUseGeneration": instance.instance_use_generation
                if instance
                else 0,
                "businessResult": business_result,
                "retainEnvironment": retain,
                "workerEnd": True,
                "workerRequest": request,
                # Only a held End carries these, so every other End keeps its exact shape.
                **({"holdForIdentity": True, "batchId": task.batch_id} if hold else {}),
            }
            now = datetime.now(UTC)
            operation = self.environments._command(
                request["commandId"],
                "saveEnvironment",
                task.project_id,
                payload["instanceId"],
                {"scope": "endTask", "projectId": task.project_id, "request": payload},
                now,
            )
            session.add(_operation_row(operation))
            session.flush()
            session.add(
                ProjectEndOperationRow(
                    id=str(uuid4()),
                    project_id=task.project_id,
                    task_id=task.id,
                    run_id=run_id,
                    phase="accepted",
                    retain_environment=wants_retain,
                    save_operation_id=None,
                    intended_result=payload,
                    targets=targets,
                    association_result=None,
                    operation_id=operation.operation_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            SqlAlchemyWorkflowRuntimeRepository(session).transition_run(
                run_id=run_id,
                target_status="finishing",
                expected_status_revision=run.status_revision,
                expected_execution_generation=generation,
                now=now,
            )
            session.commit()
            return {"endOperationId": operation.operation_id, "phase": "accepted"}

    def operation(self, run_id: str) -> Any:
        with self.sessions() as session:
            end = session.scalar(
                select(ProjectEndOperationRow).where(ProjectEndOperationRow.run_id == run_id)
            )
            operation = None if end is None else session.get(ProjectOperationRow, end.operation_id)
            return ((_operation(operation), end.intended_result) if operation and end else None)

    def finalize(self, run_id: str) -> Any:
        saved = self.operation(run_id)
        if saved is None:
            return None
        operation, payload = saved
        if operation.result is not None:
            return payload["businessResult"], operation.result, operation.error
        result, completed, _replayed = self.environments.end(
            operation.project_id, operation.idempotency_key, payload
        )
        return payload["businessResult"], result, completed.error

    def recover(self, run_id: str) -> Any:
        """Read committed stages only; a fenced run cannot publish a new save."""
        saved = self.operation(run_id)
        if saved is None:
            return None
        operation, payload = saved
        if operation.result is not None:
            return payload["businessResult"], operation.result, operation.error
        save = self.environments.environments.operation_by_key(
            f"end-save:{operation.operation_id}"
        )
        if save is not None and save.result is not None:
            outcome, error = save.result, save.error
        else:
            outcome = {
                "complete": False,
                "phase": "failed",
                "saved": None,
                "targets": payload["retainEnvironment"]["recordTargets"],
                "conflicts": [],
            }
            error = {
                "code": "END_INTERRUPTED",
                "message": "End 在完成前中断，保留原环境与操作记录供核验",
            }
        if save is not None and save.result is None:
            verified = self._published_save(save, payload)
            if verified is not None:
                outcome, error = verified
            else:
                save_ledger = self.environments.environments.save_by_operation(
                    save.operation_id
                )
                if save_ledger is not None:
                    self.environments.environments.record_save(
                        save_ledger["id"],
                        save.project_id,
                        save_ledger["instanceId"],
                        save_ledger["environmentId"],
                        save_ledger["mode"],
                        "failed",
                        save_ledger["expectedContentGeneration"],
                        save_ledger["publishedContentGeneration"],
                        save_ledger["candidateDigest"],
                        save_ledger["name"],
                        save.operation_id,
                        datetime.now(UTC),
                    )
                self.environments.environments.complete_operation(
                    save, outcome, error, datetime.now(UTC)
                )
        ledger = self.environments.environments.end_by_operation(operation.operation_id)
        if ledger is None:
            raise ProjectError("END_ACCESS_REVOKED", "End 持久记录不存在", 409)
        self.environments.environments.record_end(
            ledger["id"],
            operation.project_id,
            payload["taskId"],
            run_id,
            outcome["phase"],
            payload["retainEnvironment"]["enabled"],
            save.operation_id
            if save
            and self.environments.environments.save_by_operation(save.operation_id)
            else None,
            payload,
            payload["retainEnvironment"]["recordTargets"],
            outcome,
            operation.operation_id,
            datetime.now(UTC),
        )
        self.environments.environments.complete_operation(
            operation, outcome, error, datetime.now(UTC)
        )
        return payload["businessResult"], outcome, error

    def _published_save(self, save: Any, payload: dict[str, Any]) -> Any:
        from autoflow.application.environments.retention import _SAVE_NAMESPACE
        from autoflow.infrastructure.database.environment_models import (
            ProjectEnvironmentRow,
        )
        from autoflow.infrastructure.database.project_data_models import DataRecordRow

        ledger = self.environments.environments.save_by_operation(save.operation_id)
        if ledger is None:
            return None
        environment_id = (
            ledger["environmentId"]
            if ledger["mode"] == "update"
            else str(uuid5(_SAVE_NAMESPACE, save.operation_id))
        )
        with self.sessions() as session:
            environment = session.get(ProjectEnvironmentRow, environment_id)
            if (
                environment is None
                or environment.project_id != save.project_id
                or environment.current_digest != ledger["candidateDigest"]
            ):
                return None
            generation = (
                (ledger["expectedContentGeneration"] or 0) + 1
                if ledger["mode"] == "update"
                else 1
            )
            if environment.content_generation != generation:
                return None
            directory = self.environments.store.generation_dir(environment_id, generation)
            try:
                verified = (
                    directory.is_dir()
                    and (directory / ".digest").read_text(encoding="utf-8").strip()
                    == ledger["candidateDigest"]
                    and self.environments.store.digest(directory)
                    == ledger["candidateDigest"]
                )
            except (OSError, ValueError):
                verified = False
            targets = payload["retainEnvironment"]["recordTargets"]
            linked = verified
            for target in targets:
                ref = target["recordRef"]
                record = session.get(
                    DataRecordRow,
                    (
                        ref["datasetGeneration"],
                        ref["recordKey"]["type"],
                        ref["recordKey"]["value"],
                    ),
                )
                if (
                    record is None
                    or record.deleted
                    or record.project_id != save.project_id
                    or record.table_id != ref["tableId"]
                    or record.current_environment_id != environment_id
                    or record.link_revision
                    not in {
                        target["expectedLinkRevision"],
                        target["expectedLinkRevision"] + 1,
                    }
                ):
                    linked = False
            saved = {
                "projectId": environment.project_id,
                "environmentId": environment.id,
                "contentGeneration": environment.content_generation,
                "metadataRevision": environment.metadata_revision,
            }
        outcome = {
            "complete": linked,
            "phase": "failed"
            if not verified
            else "completed"
            if linked
            else "saved_unlinked",
            "saved": saved,
            "source": saved,
            "instance": None,
            "targets": [target["recordRef"] for target in targets],
            "conflicts": [],
        }
        error: dict[str, Any] | None = (
            None
            if linked
            else {
                "code": "SAVED_UNLINKED",
                "message": "上下文已保存，重启核验未能确认完整记录关联",
            }
        )
        if not verified:
            error = {
                "code": "ENVIRONMENT_INTEGRITY_FAILED",
                "message": "已发布环境目录缺失或摘要不一致，不能确认可恢复上下文",
                "details": saved,
            }
        outcome["error"] = error
        self.environments.environments.record_save(
            ledger["id"],
            save.project_id,
            ledger["instanceId"],
            environment_id,
            ledger["mode"],
            outcome["phase"],
            ledger["expectedContentGeneration"],
            generation,
            ledger["candidateDigest"],
            ledger["name"],
            save.operation_id,
            datetime.now(UTC),
        )
        self.environments.environments.complete_operation(
            save, outcome, error, datetime.now(UTC)
        )
        return outcome, error
