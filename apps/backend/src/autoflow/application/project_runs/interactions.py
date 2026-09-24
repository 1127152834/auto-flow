"""Project ownership and durable receipts around the migrated worker command bus."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.application.workflows.webhooks import webhook_payload
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.domain.workflows.runtime import CoreRun, WorkflowRuntimeError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

UI_REQUESTS = {"execution:input_prompt", "execution:js_script"}
REQUESTS = UI_REQUESTS | {"execution:webhook_waiting"}


class ProjectRunInteractions:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        send: Callable[[str, int, dict[str, Any]], Awaitable[None]],
    ) -> None:
        self._sessions = sessions
        self._send = send
        # Temporary UI requests die with their worker; only receipts are durable.
        self._requests: dict[tuple[str, int, str], dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def public_event(event: dict[str, Any]) -> dict[str, Any]:
        if event.get("kind") != "interaction":
            return event
        payload = event.get("payload", {})
        # Resolved defaults, script code and variables belong in the scoped request
        # response, never the persisted log/SSE stream (including password defaults).
        allowed = {"type", "requestId", "commandId", "status", "executionContext"}
        return {
            **event,
            "payload": {key: value for key, value in payload.items() if key in allowed},
        }

    def observe(self, event: dict[str, Any]) -> None:
        if event.get("kind") != "interaction":
            return
        payload = event.get("payload", {})
        request_id = payload.get("requestId")
        if not isinstance(request_id, str):
            return
        key = (event["runId"], event["executionGeneration"], request_id)
        if payload.get("type") in REQUESTS:
            self._requests.setdefault(
                key, {**copy.deepcopy(payload), "status": "pending"}
            )
        elif payload.get("type") in {
            "execution:input_prompt_closed",
            "execution:js_script_closed",
            "execution:webhook_closed",
        }:
            # Drop actual values immediately; the persisted close event is evidence.
            self._requests.pop(key, None)

    def pending(self) -> list[dict[str, Any]]:
        result = []
        with self._sessions() as session:
            for (run_id, generation, request_id), state in list(self._requests.items()):
                if state["type"] not in UI_REQUESTS:
                    continue
                task = session.scalar(select(ProjectTaskRow).where(ProjectTaskRow.run_id == run_id))
                if task is None:
                    continue
                run = self._scope(session, task.project_id, task.id)
                if run.status == "running" and run.execution_generation == generation:
                    result.append({"projectId": task.project_id, "taskId": task.id,
                                   "runId": run_id, "executionGeneration": generation,
                                   "requestId": request_id, "type": state["type"],
                                   "status": state["status"]})
        return result

    def request(self, project_id: str, task_id: str, request_id: str) -> dict[str, Any]:
        with self._sessions() as session:
            run = self._scope(session, project_id, task_id)
            state = self._requests.get((run.id, run.execution_generation, request_id))
            if run.status != "running":
                return {"requestId": request_id, "status": "cancelled"}
            if state is None or state["type"] not in UI_REQUESTS:
                raise ProjectRunError(
                    "INTERACTION_EXPIRED", "交互请求不存在或已结束", 410
                )
            return {
                **copy.deepcopy(state),
                "runId": run.id,
                "executionGeneration": run.execution_generation,
            }

    def command(self, project_id: str, task_id: str, command_id: str) -> dict[str, Any]:
        with self._sessions() as session:
            run = self._scope(session, project_id, task_id)
            row = session.get(ProjectOperationRow, command_id)
            if (
                row is None
                or row.project_id != project_id
                or row.resource.get("taskId") != task_id
                or row.kind != "workflowInteraction"
            ):
                raise ProjectRunError("NOT_FOUND", "交互命令不存在", 404)
            status = (
                "applied"
                if row.status == "succeeded"
                else "unconfirmed"
                if row.status == "failed"
                else "accepted"
            )
            if status == "accepted" and (
                run.status != "running"
                or row.resource["executionGeneration"] != run.execution_generation
            ):
                status = "unconfirmed"
            return {
                "commandId": command_id,
                "requestId": row.resource["requestId"],
                "status": status,
            }

    async def submit(
        self,
        project_id: str,
        task_id: str,
        command_id: str,
        generation: int,
        event: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate(event, data)
        if type(generation) is not int or generation < 0:
            raise ProjectRunError("VALIDATION_ERROR", "执行代次无效", 422)
        digest = hashlib.sha256(
            json.dumps(
                {
                    "projectId": project_id,
                    "taskId": task_id,
                    "commandId": command_id,
                    "generation": generation,
                    "event": event,
                    "data": data,
                },
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        async with self._lock:
            with self._sessions() as session:
                run = self._scope(session, project_id, task_id)
                existing = session.scalar(
                    select(ProjectOperationRow).where(
                        ProjectOperationRow.idempotency_key == command_id
                    )
                )
                if existing is not None:
                    if (
                        existing.kind != "workflowInteraction"
                        or existing.request_digest != digest
                    ):
                        raise ProjectRunError(
                            "IDEMPOTENCY_CONFLICT", "命令标识已用于不同请求", 409
                        )
                    return self.command(project_id, task_id, existing.id)
                if run.execution_generation != generation or run.status != "running":
                    raise ProjectRunError(
                        "INTERACTION_EXPIRED", "运行或执行代次已结束", 409
                    )
                state = self._requests.get((run.id, generation, data["requestId"]))
                if state is None or state["status"] not in {"pending", "claimed"}:
                    raise ProjectRunError(
                        "INTERACTION_EXPIRED", "交互请求不存在或已提交", 409
                    )
                expected_type = {
                    "input_prompt_result": "execution:input_prompt",
                    "webhook_result": "execution:webhook_waiting",
                }.get(event, "execution:js_script")
                if state["type"] != expected_type:
                    raise ProjectRunError(
                        "INTERACTION_CONFLICT", "命令与请求类型不符", 409
                    )
                if event == "js_script_result" and (
                    state["status"] != "claimed"
                    or state.get("claimId") != data["claimId"]
                ):
                    raise ProjectRunError(
                        "INTERACTION_CONFLICT", "脚本结果不属于当前领取者", 409
                    )
                if event == "js_script_claim" and state.get("claimId") not in {
                    None,
                    data["claimId"],
                }:
                    raise ProjectRunError(
                        "INTERACTION_CONFLICT", "脚本已由其它客户端领取", 409
                    )
                now = datetime.now(UTC)
                claimed = event == "js_script_claim"
                session.add(
                    ProjectOperationRow(
                        id=command_id,
                        project_id=project_id,
                        idempotency_key=command_id,
                        kind="workflowInteraction",
                        request_digest=digest,
                        status="succeeded" if claimed else "running",
                        status_revision=1,
                        resource={
                            "type": "workflowInteraction",
                            "projectId": project_id,
                            "taskId": task_id,
                            "runId": run.id,
                            "executionGeneration": generation,
                            "requestId": data["requestId"],
                            "event": event,
                        },
                        result=None,
                        error=None,
                        created_at=now,
                        updated_at=now,
                        completed_at=now if claimed else None,
                    )
                )
                session.commit()
                run_id = run.id
            if claimed:
                state.update(status="claimed", claimId=data["claimId"])
            else:
                # Reserve before any await. Lost send/ACK is queried, never replayed.
                state["status"] = "submitted"
                state["commandId"] = command_id
                await self._send(
                    run_id,
                    generation,
                    {"type": event, "commandId": command_id, **copy.deepcopy(data)},
                )
            return self.command(project_id, task_id, command_id)

    def has_webhook(self, webhook_id: str) -> bool:
        return any(state.get("webhookId") == webhook_id for state in self._requests.values()
                   if state["type"] == "execution:webhook_waiting")

    async def trigger_webhook(self, webhook_id: str, *, method: str, headers: Mapping[str, str],
                              query: Mapping[str, str], body: Any) -> tuple[Any, int]:
        candidates = [(key, state) for key, state in self._requests.items()
                      if state["type"] == "execution:webhook_waiting" and state.get("webhookId") == webhook_id]
        if not candidates:
            raise WorkflowRunError("WEBHOOK_NOT_FOUND", "Webhook不存在或已经结束", 404)
        if len(candidates) != 1:
            raise WorkflowRunError("WEBHOOK_AMBIGUOUS", "多个运行使用相同Webhook ID，请使用不同标识", 409)
        (run_id, generation, request_id), state = candidates[0]
        data = webhook_payload(state, method=method, headers=headers, query=query, body=body)
        with self._sessions() as session:
            task = session.scalar(select(ProjectTaskRow).where(ProjectTaskRow.run_id == run_id))
            if task is None:
                raise WorkflowRunError("WEBHOOK_NOT_FOUND", "Webhook所属任务不存在", 404)
            project_id, task_id = task.project_id, task.id
        command_id = str(uuid4())
        try:
            await self.submit(project_id, task_id, command_id, generation, "webhook_result",
                              {"requestId": request_id, "data": data})
        except WorkflowRuntimeError as error:
            if error.code == "INTERACTION_UNCONFIRMED":
                raise WorkflowRunError("WEBHOOK_DELIVERY_UNCONFIRMED", "Webhook已接收，但运行进程未确认", 503) from error
            raise
        except ProjectRunError as error:
            if error.code in {"INTERACTION_EXPIRED", "NOT_FOUND"}:
                raise WorkflowRunError("WEBHOOK_NOT_FOUND", "Webhook不存在或已经结束", 404) from error
            raise
        # Reuse the durable worker-confirmed receipt; accepted HTTP is not delivery.
        try:
            async with asyncio.timeout(10):
                while True:
                    receipt = self.command(project_id, task_id, command_id)
                    if receipt["status"] == "applied":
                        return copy.deepcopy(state.get("responseBody") or {"success": True}), int(state["responseStatus"])
                    if receipt["status"] == "unconfirmed":
                        break
                    await asyncio.sleep(.01)
        except TimeoutError:
            pass
        raise WorkflowRunError("WEBHOOK_DELIVERY_UNCONFIRMED", "Webhook已接收，但运行进程未确认", 503)

    def confirm(self, session: Session, event: dict[str, Any]) -> None:
        payload = event.get("payload", {})
        if (
            event.get("kind") != "interaction"
            or payload.get("type") != "execution:command_applied"
        ):
            return
        row = session.get(ProjectOperationRow, payload.get("commandId"))
        if (
            row is None
            or row.kind != "workflowInteraction"
            or any(
                row.resource.get(key) != value
                for key, value in {
                    "runId": event["runId"],
                    "executionGeneration": event["executionGeneration"],
                    "requestId": payload.get("requestId"),
                }.items()
            )
        ):
            raise ProjectRunError(
                "INTERACTION_ACK_INVALID", "运行进程确认了未知交互命令", 409
            )
        if row.status != "succeeded":
            row.status = "succeeded"
            row.status_revision += 1
            row.updated_at = row.completed_at = datetime.now(UTC)

    def finish(self, session: Session, run: CoreRun) -> None:
        if not run.terminal:
            return
        for row in session.scalars(
            select(ProjectOperationRow).where(
                ProjectOperationRow.kind == "workflowInteraction",
                ProjectOperationRow.status == "running",
                ProjectOperationRow.resource["runId"].as_string() == run.run_id,
            )
        ):
            row.status = "failed"
            row.status_revision += 1
            row.error = {
                "code": "INTERACTION_UNCONFIRMED",
                "message": "运行已结束，未收到交互命令应用确认",
            }
            row.updated_at = row.completed_at = datetime.now(UTC)

    def forget_run(self, run_id: str) -> None:
        for key in list(self._requests):
            if key[0] == run_id:
                del self._requests[key]

    @staticmethod
    def _scope(session: Session, project_id: str, task_id: str) -> WorkflowRunRow:
        project = session.get(ProjectRow, project_id)
        task = session.get(ProjectTaskRow, task_id)
        if (
            project is None
            or project.lifecycle_state == "deleted"
            or task is None
            or task.project_id != project_id
        ):
            raise ProjectRunError("NOT_FOUND", "项目任务不存在", 404)
        run = session.get(WorkflowRunRow, task.run_id)
        if run is None:
            raise ProjectRunError("RUN_FACTS_INCOMPLETE", "运行证据不完整", 409)
        return run

    @staticmethod
    def _validate(event: str, data: dict[str, Any]) -> None:
        valid = isinstance(data.get("requestId"), str) and bool(data["requestId"])
        if event == "input_prompt_result":
            valid = (
                valid
                and set(data) == {"requestId", "value"}
                and (data["value"] is None or isinstance(data["value"], str))
            )
        elif event == "webhook_result":
            valid = valid and set(data) == {"requestId", "data"} and isinstance(data.get("data"), dict)
        elif event == "js_script_claim":
            valid = (
                valid
                and set(data) == {"requestId", "claimId"}
                and isinstance(data.get("claimId"), str)
                and bool(data["claimId"])
            )
        elif event == "js_script_result":
            valid = (
                valid
                and set(data)
                <= {"requestId", "claimId", "success", "result", "variables", "error"}
                and isinstance(data.get("claimId"), str)
                and bool(data["claimId"])
                and isinstance(data.get("success"), bool)
            )
            valid = valid and (
                isinstance(data.get("variables"), dict)
                if data.get("success")
                else isinstance(data.get("error"), str) and bool(data["error"].strip())
            )
        else:
            valid = False
        try:
            json.dumps(data, allow_nan=False)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ProjectRunError("VALIDATION_ERROR", "交互命令格式无效", 422)
