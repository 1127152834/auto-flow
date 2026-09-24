"""Studio assistant sessions backed by LangGraph and the managed model service."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.domain.models import ModelError, ModelInvocationResult
from autoflow.domain.workflows.assistant import AssistantSession
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.credentials.redaction import redact_sensitive_value
from autoflow.infrastructure.database.workflow_assistant import (
    SqlAlchemyWorkflowAssistant,
)
from autoflow.infrastructure.filesystem.assistant_files import AssistantFileStore
from autoflow.providers.assistant import (
    AssistantGraph,
    AssistantGraphResult,
    AssistantModelReply,
    AssistantToolCall,
)


class ManagedModels(Protocol):
    async def invoke(
        self, model_id: str, payload: dict[str, Any]
    ) -> ModelInvocationResult: ...


class McpTools(Protocol):
    def tool_schemas(self) -> list[dict[str, Any]]: ...

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...


def _now() -> datetime:
    return datetime.now(UTC)


def _message(role: str, content: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": uuid4().hex[:12],
        "role": role,
        "content": content,
        "timestamp": _now().isoformat(),
        **extra,
    }


def _tool_payload(call: AssistantToolCall, status: str = "running") -> dict[str, Any]:
    return {
        "id": call.id,
        "name": call.name,
        "arguments": copy.deepcopy(call.arguments),
        "status": status,
    }


class WorkflowAssistantService:
    def __init__(
        self,
        repository: SqlAlchemyWorkflowAssistant,
        checkpoint_path: Path,
        models: ManagedModels,
        events: StudioEventJournal,
        mcp: McpTools | None = None,
    ) -> None:
        self._repository = repository
        self._models = models
        self._events = events
        self._mcp = mcp
        self._files = AssistantFileStore(checkpoint_path.parent)
        self._graph = AssistantGraph(
            checkpoint_path, self._invoke_model, self._protect_graph_value
        )
        self._waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._tasks: dict[str, asyncio.Task[AssistantGraphResult]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _invoke_model(
        self, model_id: str, payload: dict[str, Any]
    ) -> AssistantModelReply:
        provider_payload = dict(payload)
        fallback_ids = provider_payload.pop("fallbackModelIds", [])
        session_id = provider_payload.pop("_assistantSessionId", None)

        async def on_chunk(kind: str, delta: str, full: str) -> None:
            if isinstance(session_id, str):
                protected_delta = self._protect_graph_value(delta)
                protected_full = self._protect_graph_value(full)
                event = {
                    "session_id": session_id,
                    "delta": self._inline_or_summary(protected_delta),
                    "full": self._inline_or_summary(protected_full),
                }
                if isinstance(protected_full, dict):
                    event.update(protected_full)
                await self._events.publish(
                    f"ai_assistant:{kind}_partial",
                    event,
                )

        provider_payload["_onChunk"] = on_chunk
        tools = provider_payload.get("tools")
        if isinstance(tools, list) and self._mcp is not None:
            provider_payload["tools"] = [*tools, *self._mcp.tool_schemas()]
        messages = provider_payload.get("messages")
        if isinstance(messages, list):
            provider_payload["messages"] = self._files.hydrate_model_messages(messages)
        model_ids = list(dict.fromkeys([model_id, *fallback_ids]))
        last_error: ModelError | None = None
        for candidate in model_ids:
            try:
                result = await self._models.invoke(candidate, provider_payload)
                break
            except ModelError as error:
                last_error = error
        else:
            assert last_error is not None
            raise last_error
        return AssistantModelReply(
            content=result.content,
            reasoning=result.reasoning,
            tool_calls=tuple(
                AssistantToolCall(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    arguments=dict(item["arguments"]),
                )
                for item in result.tool_calls
            ),
        )

    async def chat(
        self,
        *,
        session_id: str,
        message: str,
        model_id: str,
        enable_tools: bool,
        workflow_context: dict[str, Any],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        images: list[str] | None = None,
        fallback_model_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if not message.strip():
            raise WorkflowRunError("ASSISTANT_MESSAGE_REQUIRED", "消息不能为空", 422)
        safe_message = str(redact_sensitive_value(message))
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            session = self._repository.get(session_id) or self._repository.create(
                session_id, safe_message.strip()[:24] or "新对话", now=_now()
            )
            if session.status in {"running", "waiting_for_action"}:
                raise WorkflowRunError(
                    "ASSISTANT_SESSION_BUSY", "小助手正在处理上一条消息", 409
                )
            stored_images = await asyncio.to_thread(
                self._files.store_images, list(images or [])
            )
            user = self._stored_text_message(
                "user", safe_message, images=stored_images
            )
            session = self._repository.save(
                session.with_changes(
                    messages=(*session.messages, user),
                    status="running",
                    pending_action=None,
                )
            )
            graph_messages = []
            for item in session.messages:
                if item.get("role") not in {"user", "assistant", "tool"}:
                    continue
                content: Any = item.get("contentRef", item.get("content", ""))
                attached = item.get("images")
                if (
                    item.get("role") == "user"
                    and isinstance(attached, list)
                    and attached
                ):
                    content = [
                        {"type": "text", "text": str(content)},
                        *[
                            {"type": "image_url", "image_url": {"url": image}}
                            for image in attached
                            if isinstance(image, str)
                        ],
                    ]
                graph_messages.append({"role": item["role"], "content": content})
            context = json.dumps(
                redact_sensitive_value(workflow_context),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            prompt = "你是 AutoFlow Studio 小助手。只能使用提供的工具，前端确认前不得声称操作成功。"
            if system_prompt.strip():
                prompt += "\n" + str(redact_sensitive_value(system_prompt.strip()))
            prompt += "\n当前工作流上下文：" + context
            protected_prompt = self._protect_graph_value(prompt)
            graph_messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        protected_prompt["artifactRef"]
                        if isinstance(protected_prompt, dict)
                        else str(protected_prompt)
                    ),
                },
            )
            waiter = asyncio.get_running_loop().create_future()
            self._waiters[session_id] = waiter
            task = asyncio.create_task(
                self._graph.start(
                    thread_id=f"assistant/{session_id}",
                    session_id=session_id,
                    model_id=model_id,
                    messages=graph_messages,
                    enable_tools=enable_tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    fallback_model_ids=fallback_model_ids,
                )
            )
            self._tasks[session_id] = task
        try:
            result = await task
            response = await self._apply_graph_result(session_id, result)
            if response is not None:
                return response
            return await waiter
        except asyncio.CancelledError:
            if waiter.done() and not waiter.cancelled():
                return waiter.result()
            raise
        finally:
            if self._tasks.get(session_id) is task:
                self._tasks.pop(session_id, None)
            if waiter.done() or waiter.cancelled():
                self._waiters.pop(session_id, None)

    async def _apply_graph_result(
        self, session_id: str, result: AssistantGraphResult
    ) -> dict[str, Any] | None:
        session = self._required(session_id)
        if session.status == "cancelled":
            return {
                "session_id": session_id,
                "message": copy.deepcopy(session.messages[-1]),
            }
        if result.status == "waiting_for_action":
            assert result.tool_call is not None and result.command_id is not None
            call = result.tool_call
            assistant = _message("assistant", "", tool_calls=[_tool_payload(call)])
            is_mcp = call.name.startswith("mcp__")
            available_mcp_tools = (
                {
                    str(schema.get("function", {}).get("name"))
                    for schema in self._mcp.tool_schemas()
                }
                if self._mcp is not None
                else set()
            )
            if is_mcp and call.name not in available_mcp_tools:
                return await self._apply_graph_result(
                    session_id,
                    AssistantGraphResult(
                        status="failed", error=f"MCP 工具未连接或不存在: {call.name}"
                    ),
                )
            pending = {
                "commandId": call.id,
                "action": call.name if is_mcp else call.arguments["action"],
                "payload": copy.deepcopy(
                    call.arguments if is_mcp else call.arguments.get("payload", {})
                ),
                "kind": "mcp" if is_mcp else "client_action",
            }
            self._repository.save(
                session.with_changes(
                    messages=(*session.messages, assistant),
                    status="waiting_for_action",
                    pending_action=pending,
                )
            )
            await self._events.publish(
                "ai_assistant:assistant_partial",
                {"session_id": session_id, "message": copy.deepcopy(assistant)},
            )
            await self._events.publish(
                "ai_assistant:tool_call",
                {"session_id": session_id, "tool_call": _tool_payload(call)},
            )
            await self._events.publish(
                "ai_assistant:mcp_tool_request"
                if is_mcp
                else "ai_assistant:client_action_request",
                {
                    "session_id": session_id,
                    "tool_call_id": call.id,
                    "action": pending["action"],
                    "payload": pending["payload"],
                },
            )
            return None
        if result.status == "failed":
            error = str(
                redact_sensitive_value(result.error or "小助手执行失败")
            )
            failed = _message("assistant", error)
            self._repository.save(
                session.with_changes(
                    messages=(*session.messages, failed),
                    status="failed",
                    pending_action=None,
                )
            )
            await self._events.publish(
                "ai_assistant:error",
                {"session_id": session_id, "error": error},
            )
            response = {"session_id": session_id, "message": failed}
        else:
            assistant = self._graph_message(result.content, result.reasoning)
            self._repository.save(
                session.with_changes(
                    messages=(*session.messages, assistant),
                    status="completed",
                    pending_action=None,
                )
            )
            await self._events.publish(
                "ai_assistant:content_partial",
                self._stream_event(session_id, result.content),
            )
            response = {"session_id": session_id, "message": assistant}
        waiter = self._waiters.get(session_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(response)
        return response

    async def submit_event_command(
        self, command_id: str, event: str, data: dict[str, Any]
    ) -> tuple[dict[str, Any], int]:
        if event != "ai_client_action_ack":
            return await self._submit_event_command_unlocked(command_id, event, data)
        session_id = data.get("session_id")
        tool_call_id = data.get("tool_call_id")
        lock_key = (
            str(session_id)
            if isinstance(session_id, str) and session_id
            else f"tool:{tool_call_id}"
        )
        lock = self._locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            return await self._submit_event_command_unlocked(command_id, event, data)

    async def _submit_event_command_unlocked(
        self, command_id: str, event: str, data: dict[str, Any]
    ) -> tuple[dict[str, Any], int]:
        if event == "ai_client_action_claim":
            return await self._claim_event_command(command_id, data)
        if event != "ai_client_action_ack":
            raise WorkflowRunError("COMMAND_NOT_FOUND", "命令不属于小助手", 404)
        tool_call_id = data.get("tool_call_id")
        requested_session_id = data.get("session_id")
        claim_command_id = data.get("claim_command_id")
        result = data.get("result")
        if (
            not isinstance(tool_call_id, str)
            or not tool_call_id
            or (
                requested_session_id is not None
                and not isinstance(requested_session_id, str)
            )
            or not isinstance(claim_command_id, str)
            or not claim_command_id
            or not isinstance(result, dict)
        ):
            return {
                "commandId": command_id,
                "success": False,
                "error": "工具结果无效",
            }, 422
        protected_request = self._compact_tool_result(result)
        fingerprint = hashlib.sha256(
            json.dumps(
                {"event": event, "data": data},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        previous = self._repository.get_command(command_id)
        if previous is not None:
            if previous.request_hash != fingerprint:
                return {
                    "commandId": command_id,
                    "success": False,
                    "error": "commandId 已用于不同请求",
                }, 409
            if previous.receipt is not None:
                return copy.deepcopy(previous.receipt), 200 if previous.receipt.get(
                    "success"
                ) else 409
        session = (
            self._repository.get(previous.session_id)
            if previous is not None
            else (
                self._repository.get(requested_session_id)
                if requested_session_id
                else self._repository.find_pending(tool_call_id)
            )
        )
        if (
            session is None
            or not session.pending_action
            or session.pending_action.get("commandId") != tool_call_id
        ) and previous is None:
            return {
                "commandId": command_id,
                "success": False,
                "error": "工具请求不存在或已结束",
            }, 409
        if session is None:
            return {
                "commandId": command_id,
                "success": False,
                "error": "助手会话不存在",
            }, 409
        pending_action = session.pending_action
        if pending_action is None:
            return {
                "commandId": command_id,
                "success": False,
                "status": "confirmed",
            }, 202
        claim = self._repository.get_command(claim_command_id)
        pending_claim_id = (
            session.pending_action.get("claimCommandId")
            if session.pending_action is not None
            else None
        )
        if (
            claim is None
            or claim.status != "completed"
            or claim.session_id != session.id
            or claim.result.get("tool_call_id") != tool_call_id
            or (previous is None and pending_claim_id != claim_command_id)
        ):
            return {
                "commandId": command_id,
                "success": False,
                "error": "工具请求尚未被认领",
            }, 409
        if previous is None:
            try:
                self._repository.confirm_command(
                    command_id,
                    session.id,
                    request_hash=fingerprint,
                    result=protected_request,
                    now=_now(),
                )
            except ValueError as error:
                return {
                    "commandId": command_id,
                    "success": False,
                    "error": str(error),
                }, 409
        if pending_action.get("kind") == "mcp":
            if result.get("success") is True:
                if self._mcp is None:
                    result = {"success": False, "error": "MCP 服务不可用"}
                else:
                    try:
                        result = {
                            "success": True,
                            "data": await self._mcp.call_tool(
                                str(pending_action["action"]),
                                dict(
                                    self._files.hydrate_value(
                                        pending_action.get("payload") or {}
                                    )
                                ),
                            ),
                        }
                    except Exception as error:  # noqa: BLE001 - tool failures return to the model.
                        result = {
                            "success": False,
                            "error": str(redact_sensitive_value(str(error)[:500])),
                        }
            else:
                result = {
                    "success": False,
                    "error": str(
                        redact_sensitive_value(
                            str(result.get("error") or "用户拒绝执行 MCP 工具")
                        )
                    ),
                }
        result = self._compact_tool_result(result)
        graph_thread = f"assistant/{session.id}"
        current_graph = await self._graph.current(thread_id=graph_thread)
        resumed = (
            await self._graph.resume(
                thread_id=graph_thread, command_id=tool_call_id, result=result
            )
            if current_graph.tool_call is not None
            and current_graph.tool_call.id == tool_call_id
            else current_graph
        )
        current = self._required(session.id)
        messages = [copy.deepcopy(item) for item in current.messages]
        for message in reversed(messages):
            calls = message.get("tool_calls")
            if not isinstance(calls, list):
                continue
            for call in calls:
                if isinstance(call, dict) and call.get("id") == tool_call_id:
                    call.update(
                        status="success" if result.get("success") is True else "failed",
                        result=copy.deepcopy(result.get("data")),
                        error=result.get("error"),
                    )
                    break
            else:
                continue
            break
        self._repository.save(current.with_changes(messages=tuple(messages)))
        await self._events.publish(
            "ai_assistant:tool_result",
            {
                "session_id": session.id,
                "tool_call": next(
                    call
                    for message in reversed(messages)
                    for call in message.get("tool_calls", [])
                    if call.get("id") == tool_call_id
                ),
            },
        )
        await self._apply_graph_result(session.id, resumed)
        receipt = {"commandId": command_id, "success": True}
        self._repository.finish_command(command_id, status="completed", receipt=receipt)
        return receipt, 200

    async def _claim_event_command(
        self, command_id: str, data: dict[str, Any]
    ) -> tuple[dict[str, Any], int]:
        session_id = data.get("session_id")
        tool_call_id = data.get("tool_call_id")
        executor_id = data.get("executor_id")
        if not all(
            isinstance(value, str) and value
            for value in (session_id, tool_call_id, executor_id)
        ):
            return {
                "commandId": command_id,
                "success": False,
                "error": "工具认领信息无效",
            }, 422
        assert isinstance(session_id, str)
        assert isinstance(tool_call_id, str)
        assert isinstance(executor_id, str)
        fingerprint = hashlib.sha256(
            json.dumps(
                {"event": "ai_client_action_claim", "data": data},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            previous = self._repository.get_command(command_id)
            if previous is not None:
                if previous.request_hash != fingerprint:
                    return {
                        "commandId": command_id,
                        "success": False,
                        "error": "commandId 已用于不同请求",
                    }, 409
                if previous.receipt is not None:
                    return copy.deepcopy(previous.receipt), 200
            session = self._repository.get(session_id)
            if (
                session is None
                or not session.pending_action
                or session.pending_action.get("commandId") != tool_call_id
            ):
                return {
                    "commandId": command_id,
                    "success": False,
                    "error": "工具请求不存在或已结束",
                }, 409
            claimed_by = session.pending_action.get("claimCommandId")
            if claimed_by is not None and claimed_by != command_id:
                return {
                    "commandId": command_id,
                    "success": False,
                    "error": "工具请求已由其他窗口认领，结果尚未确认",
                }, 409
            if previous is None:
                try:
                    self._repository.confirm_command(
                        command_id,
                        session.id,
                        request_hash=fingerprint,
                        result=copy.deepcopy(data),
                        now=_now(),
                    )
                except ValueError as error:
                    return {
                        "commandId": command_id,
                        "success": False,
                        "error": str(error),
                    }, 409
            if claimed_by is None:
                pending = copy.deepcopy(session.pending_action)
                pending["claimCommandId"] = command_id
                self._repository.save(session.with_changes(pending_action=pending))
            receipt = {"commandId": command_id, "success": True}
            self._repository.finish_command(
                command_id, status="completed", receipt=receipt
            )
            return receipt, 200

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]:
        command = self._repository.get_command(command_id)
        if command is None:
            raise WorkflowRunError("COMMAND_NOT_FOUND", "命令记录不存在", 404)
        if command.receipt is None:
            return {
                "commandId": command_id,
                "success": False,
                "status": "confirmed",
                "httpStatus": 202,
            }, 200
        return {**copy.deepcopy(command.receipt), "httpStatus": 200}, 200

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self._required(session_id)
        pending_action = copy.deepcopy(session.pending_action)
        if pending_action is not None:
            pending_action.pop("kind", None)
        return {
            "id": session.id,
            "title": session.title,
            "messages": self._files.public_messages(session.messages),
            "status": session.status,
            "pending_action": pending_action,
            "revision": session.revision,
        }

    def artifact_file(self, kind: str, artifact_id: str) -> tuple[Path, str]:
        scheme = {
            "attachment": "assistant-attachment://",
            "artifact": "assistant-artifact://",
        }.get(kind)
        if scheme is None:
            raise WorkflowRunError(
                "ASSISTANT_ARTIFACT_INVALID", "小助手产物类型无效", 422
            )
        return self._files.artifact_file(f"{scheme}{artifact_id}")

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item.id,
                "title": item.title,
                "message_count": len(item.messages),
                "updated_at": item.updated_at.isoformat(),
                "last_message_preview": next(
                    (
                        str(message.get("content", ""))[:120]
                        for message in reversed(item.messages)
                        if message.get("content")
                    ),
                    "",
                ),
            }
            for item in self._repository.list()
        ]

    def create_session(self, title: str | None = None) -> dict[str, str]:
        session = self._repository.create(
            uuid4().hex, (title or "新对话").strip() or "新对话", now=_now()
        )
        return {"session_id": session.id, "title": session.title}

    def rename_session(self, session_id: str, title: str) -> dict[str, bool]:
        session = self._required(session_id)
        if not title.strip():
            raise WorkflowRunError("ASSISTANT_TITLE_REQUIRED", "会话标题不能为空", 422)
        self._repository.save(session.with_changes(title=title.strip()))
        return {"success": True}

    def truncate_session(self, session_id: str, message_id: str) -> dict[str, Any]:
        session = self._required(session_id)
        index = next(
            (
                index
                for index, item in enumerate(session.messages)
                if item.get("id") == message_id
            ),
            None,
        )
        if index is None:
            raise WorkflowRunError("ASSISTANT_MESSAGE_NOT_FOUND", "消息不存在", 404)
        saved = self._repository.save(
            session.with_changes(
                messages=session.messages[:index], status="idle", pending_action=None
            )
        )
        return {
            "success": True,
            "messages": self._files.public_messages(saved.messages),
        }

    async def extract_file(self, filename: str, content_base64: str) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._files.extract_file, filename, content_base64
        )

    async def transcribe(
        self, audio_base64: str, language: str, model_size: str
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._files.transcribe_audio, audio_base64, language, model_size
        )

    def _protect_graph_value(self, value: Any) -> Any:
        return self._files.externalize_large_leaves(redact_sensitive_value(value))

    @staticmethod
    def _inline_or_summary(value: Any) -> str:
        if isinstance(value, dict) and isinstance(value.get("artifactRef"), str):
            return "（内容过长，已保存为小助手产物）"
        return str(value)

    def _stream_event(self, session_id: str, content: str) -> dict[str, Any]:
        if content.startswith("assistant-artifact://"):
            info = self._files.artifact_info(content)
            return {
                "session_id": session_id,
                "delta": "",
                "full": "（内容过长，已保存为小助手产物）",
                **info,
            }
        return {"session_id": session_id, "delta": "", "full": content}

    def _graph_message(self, content: str, reasoning: str) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if content.startswith("assistant-artifact://"):
            extra["contentRef"] = content
            extra["contentArtifact"] = self._files.artifact_info(content)
            content = "（内容过长，已保存为小助手产物）"
        if reasoning.startswith("assistant-artifact://"):
            extra["reasoningContentRef"] = reasoning
            extra["reasoningArtifact"] = self._files.artifact_info(reasoning)
            reasoning = "（思考内容过长，已保存为小助手产物）"
        return _message(
            "assistant", content, reasoning_content=reasoning or None, **extra
        )

    def _stored_text_message(
        self, role: str, content: str, **extra: Any
    ) -> dict[str, Any]:
        protected = self._protect_graph_value(content)
        if not isinstance(protected, dict):
            return _message(role, str(protected), **extra)
        reference = str(protected["artifactRef"])
        return _message(
            role,
            "（内容过长，已保存为小助手产物）",
            contentRef=reference,
            contentArtifact=protected,
            **extra,
        )

    def _compact_tool_result(self, result: dict[str, Any]) -> dict[str, Any]:
        protected = redact_sensitive_value(result)
        assert isinstance(protected, dict)
        if "data" in protected:
            protected["data"] = self._files.externalize(protected["data"])
        return protected

    def delete_session(self, session_id: str) -> dict[str, bool]:
        session = self._required(session_id)
        if session.status in {"running", "waiting_for_action"}:
            raise WorkflowRunError("ASSISTANT_SESSION_BUSY", "请先停止当前对话", 409)
        self._repository.delete(session_id)
        return {"success": True}

    async def cancel(self, session_id: str) -> dict[str, Any]:
        return await self._cancel_session(
            session_id,
            message="[已停止] 任务被你打断。",
            reason="user_cancelled",
        )

    async def shutdown(self) -> None:
        session_ids = set(self._tasks) | set(self._waiters)
        if session_ids:
            await asyncio.gather(
                *(
                    self._cancel_session(
                        session_id,
                        message="[已停止] 服务正在关闭。",
                        reason="service_shutdown",
                    )
                    for session_id in session_ids
                )
            )

    async def _cancel_session(
        self, session_id: str, *, message: str, reason: str
    ) -> dict[str, Any]:
        session = self._required(session_id)
        if session.status not in {"running", "waiting_for_action"}:
            return {"success": True, "session_id": session_id}
        cancelled = _message("assistant", message)
        self._repository.save(
            session.with_changes(
                messages=(*session.messages, cancelled),
                status="cancelled",
                pending_action=None,
            )
        )
        response = {"session_id": session_id, "message": cancelled}
        waiter = self._waiters.get(session_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(response)
        task = self._tasks.get(session_id)
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self._events.publish(
            "ai_assistant:cancelled", {"session_id": session_id, "reason": reason}
        )
        return {"success": True, "session_id": session_id}

    async def test_model(self, model_id: str) -> dict[str, Any]:
        started = asyncio.get_running_loop().time()
        result = await self._models.invoke(
            model_id,
            {
                "messages": [{"role": "user", "content": "只回复 OK"}],
                "maxTokens": 16,
                "timeoutSeconds": 30,
            },
        )
        return {
            "success": True,
            "message": "模型连接正常",
            "detail": result.content[:120],
            "latency_ms": round(
                (asyncio.get_running_loop().time() - started) * 1000, 2
            ),
        }

    def has_command(self, command_id: str) -> bool:
        return self._repository.get_command(command_id) is not None

    def _required(self, session_id: str) -> AssistantSession:
        session = self._repository.get(session_id)
        if session is None:
            raise WorkflowRunError(
                "ASSISTANT_SESSION_NOT_FOUND", "小助手会话不存在", 404
            )
        return session
