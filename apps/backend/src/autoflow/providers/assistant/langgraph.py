"""LangGraph orchestration for the Studio assistant.

Source behavior: WebRPA@5ccb900e, ``ai_assistant_service.py``.
AutoFlow adaptation: managed model IDs, durable local checkpoints and frontend-owned
canvas side effects.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from autoflow.domain.workflows.scope import APPROVED_NODE_TYPES


@dataclass(frozen=True, slots=True)
class AssistantToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AssistantModelReply:
    content: str
    reasoning: str
    tool_calls: tuple[AssistantToolCall, ...]


@dataclass(frozen=True, slots=True)
class AssistantGraphResult:
    status: Literal["completed", "waiting_for_action", "failed"]
    content: str = ""
    reasoning: str = ""
    command_id: str | None = None
    tool_call: AssistantToolCall | None = None
    error: str | None = None


ModelInvoker = Callable[[str, dict[str, Any]], Awaitable[AssistantModelReply]]


class _State(TypedDict, total=False):
    model_id: str
    fallback_model_ids: list[str]
    messages: list[dict[str, Any]]
    enable_tools: bool
    temperature: float
    max_tokens: int
    pending_tool_call: dict[str, Any] | None
    content: str
    reasoning: str
    error: str | None
    steps: int


_CLIENT_ACTIONS = frozenset(
    {
        "new_workflow",
        "load_workflow",
        "load_workflow_from_data",
        "save_workflow",
        "save_workflow_to_folder",
        "run_workflow",
        "run_workflow_headless",
        "run_single_node",
        "stop_workflow",
        "export_workflow",
        "add_nodes",
        "delete_node",
        "delete_nodes",
        "update_node_config",
        "bulk_update_nodes",
        "focus_node",
        "toggle_node_disabled",
        "align_nodes",
        "auto_layout",
        "copy_nodes",
        "paste_nodes",
        "move_node",
        "rename_node",
        "find_nodes_by_type",
        "connect_nodes",
        "disconnect_edge",
        "auto_connect_chain",
        "connect_branches",
        "select_all_nodes",
        "clear_selection",
        "fit_view",
        "replace_module_type",
        "duplicate_node",
        "undo",
        "redo",
        "rename_workflow",
        "add_variable",
        "update_variable",
        "delete_variable",
        "rename_variable",
        "list_variables",
        "get_variable",
        "change_variable_type",
        "clear_variables",
        "get_workflow_detail",
        "get_logs",
        "clear_logs",
        "export_logs",
        "set_verbose_log",
        "set_max_log_count",
        "get_node_runtime_errors",
        "get_collected_data",
        "set_collected_data",
        "add_data_rows",
        "add_data_row",
        "add_data_column",
        "delete_data_row",
        "delete_data_column",
        "set_data_cell",
        "clear_data",
        "download_data",
        "upload_image",
        "list_image_assets",
        "delete_image_asset",
        "rename_image_asset",
        "switch_bottom_panel",
        "list_local_workflows",
        "get_local_workflow_content",
        "delete_local_workflow",
        "get_local_workflow_default_folder",
        "list_scheduled_tasks_full",
        "get_scheduled_task_detail",
        "create_scheduled_task",
        "update_scheduled_task",
        "delete_scheduled_task",
        "toggle_scheduled_task",
        "execute_scheduled_task",
        "stop_scheduled_task",
        "get_scheduled_task_logs",
        "clear_scheduled_task_logs",
        "get_scheduled_task_statistics",
        "get_global_config",
        "reset_global_config",
        "update_global_config",
        "open_global_config",
        "close_global_config",
        "open_local_workflow_dialog",
        "close_local_workflow_dialog",
        "open_scheduled_tasks",
        "close_scheduled_tasks",
        "open_documentation",
        "close_documentation",
        "open_auto_browser",
        "close_auto_browser",
        "open_variable_tracking",
        "close_variable_tracking",
        "open_export_dialog",
        "open_module_search",
        "take_screenshot",
        "capture_editor_screenshot",
        "show_toast",
        "add_log",
        "list_open_dialogs",
        "respond_to_dialog",
        "dismiss_dialog",
    }
)


def _tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "client_action",
                "description": "请求 Studio 前端读取或修改当前工作流，结果确认后才能继续。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": sorted(_CLIENT_ACTIONS)},
                        "payload": {"type": "object"},
                    },
                    "required": ["action"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def _node_types(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for node in value:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        raw = data.get("moduleType") if isinstance(data, dict) else None
        module_type = raw if isinstance(raw, str) and raw else node.get("type")
        if isinstance(module_type, str) and module_type not in {
            "moduleNode",
            "noteNode",
            "groupNode",
            "subflowHeaderNode",
        }:
            result.append(module_type)
    return result


def _validate_tool_call(call: AssistantToolCall) -> str | None:
    if call.name != "client_action":
        return f"助手工具未获批准: {call.name}"
    action = call.arguments.get("action")
    payload = call.arguments.get("payload", {})
    if not isinstance(action, str) or action not in _CLIENT_ACTIONS:
        return f"助手操作未获批准: {action}"
    if not isinstance(payload, dict):
        return "助手操作参数必须是对象"
    node_types: list[str] = []
    if action in {"add_nodes", "load_workflow_from_data"}:
        node_types.extend(_node_types(payload.get("nodes")))
    if action == "replace_module_type":
        replacement = payload.get("new_type")
        if isinstance(replacement, str):
            node_types.append(replacement)
    excluded = sorted({item for item in node_types if item not in APPROVED_NODE_TYPES})
    if excluded:
        return f"助手请求包含未批准的节点类型: {', '.join(excluded)}"
    return None


class AssistantGraph:
    def __init__(self, checkpoint_path: Path, invoke_model: ModelInvoker) -> None:
        self._checkpoint_path = Path(checkpoint_path)
        self._invoke_model = invoke_model

    def _builder(self) -> StateGraph[_State]:
        async def call_model(state: _State) -> _State:
            steps = int(state.get("steps", 0)) + 1
            if steps > 16:
                return {**state, "steps": steps, "error": "助手工具调用轮次超过上限"}
            payload: dict[str, Any] = {
                "messages": state["messages"],
                "temperature": state["temperature"],
                "maxTokens": state["max_tokens"],
                "fallbackModelIds": state.get("fallback_model_ids", []),
            }
            if state.get("enable_tools"):
                payload["tools"] = _tool_schema()
                payload["toolChoice"] = "auto"
            reply = await self._invoke_model(state["model_id"], payload)
            messages = list(state["messages"])
            assistant: dict[str, Any] = {
                "role": "assistant",
                "content": reply.content,
            }
            if reply.tool_calls:
                assistant["tool_calls"] = [
                    {
                        "id": item.id,
                        "type": "function",
                        "function": {
                            "name": item.name,
                            "arguments": json.dumps(
                                item.arguments,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        },
                    }
                    for item in reply.tool_calls
                ]
            messages.append(assistant)
            if len(reply.tool_calls) > 1:
                return {**state, "messages": messages, "steps": steps, "error": "一次只允许一个画布工具请求"}
            if reply.tool_calls:
                call = reply.tool_calls[0]
                error = _validate_tool_call(call)
                if error:
                    return {**state, "messages": messages, "steps": steps, "error": error}
                return {
                    **state,
                    "messages": messages,
                    "steps": steps,
                    "pending_tool_call": {
                        "id": call.id,
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                    "content": "",
                    "reasoning": reply.reasoning,
                }
            return {
                **state,
                "messages": messages,
                "steps": steps,
                "pending_tool_call": None,
                "content": reply.content,
                "reasoning": reply.reasoning,
                "error": None,
            }

        def wait_for_action(state: _State) -> _State:
            call = state["pending_tool_call"]
            assert call is not None
            result = interrupt(
                {
                    "commandId": call["id"],
                    "toolCall": call,
                }
            )
            messages = list(state["messages"])
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(
                        result,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
            return {**state, "messages": messages, "pending_tool_call": None}

        def after_model(state: _State) -> str:
            if state.get("error") or state.get("pending_tool_call") is None:
                return END
            return "action"

        graph = StateGraph(_State)
        graph.add_node("model", call_model)
        graph.add_node("action", wait_for_action)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", after_model)
        graph.add_edge("action", "model")
        return graph

    async def start(
        self,
        *,
        thread_id: str,
        model_id: str,
        messages: list[dict[str, Any]],
        enable_tools: bool,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        fallback_model_ids: list[str] | None = None,
    ) -> AssistantGraphResult:
        if not thread_id or not model_id:
            raise ValueError("助手会话和模型不能为空")
        initial: _State = {
            "model_id": model_id,
            "fallback_model_ids": list(fallback_model_ids or []),
            "messages": messages,
            "enable_tools": enable_tools,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "pending_tool_call": None,
            "content": "",
            "reasoning": "",
            "error": None,
            "steps": 0,
        }
        return await self._invoke(thread_id, initial)

    async def resume(
        self,
        *,
        thread_id: str,
        command_id: str,
        result: dict[str, Any],
    ) -> AssistantGraphResult:
        async with AsyncSqliteSaver.from_conn_string(
            str(self._checkpoint_path)
        ) as checkpointer:
            graph = self._builder().compile(checkpointer=checkpointer)
            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
            snapshot = await graph.aget_state(config)
            pending = snapshot.values.get("pending_tool_call")
            if not isinstance(pending, dict) or pending.get("id") != command_id:
                raise ValueError("工具命令身份不匹配")
            output = await graph.ainvoke(Command(resume=result), config=config)
        return self._result(output)

    async def current(self, *, thread_id: str) -> AssistantGraphResult:
        async with AsyncSqliteSaver.from_conn_string(
            str(self._checkpoint_path)
        ) as checkpointer:
            graph = self._builder().compile(checkpointer=checkpointer)
            snapshot = await graph.aget_state(
                {"configurable": {"thread_id": thread_id}}
            )
        if not snapshot.values:
            raise ValueError("助手检查点不存在")
        return self._result(dict(snapshot.values))

    async def _invoke(
        self, thread_id: str, value: _State | Command[Any]
    ) -> AssistantGraphResult:
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(
            str(self._checkpoint_path)
        ) as checkpointer:
            graph = self._builder().compile(checkpointer=checkpointer)
            output = await graph.ainvoke(
                value,
                config={"configurable": {"thread_id": thread_id}},
            )
        return self._result(output)

    @staticmethod
    def _result(output: dict[str, Any]) -> AssistantGraphResult:
        error = output.get("error")
        if isinstance(error, str) and error:
            return AssistantGraphResult(status="failed", error=error)
        pending = output.get("pending_tool_call")
        if isinstance(pending, dict):
            call = AssistantToolCall(
                id=str(pending["id"]),
                name=str(pending["name"]),
                arguments=dict(pending["arguments"]),
            )
            return AssistantGraphResult(
                status="waiting_for_action",
                command_id=call.id,
                tool_call=call,
            )
        return AssistantGraphResult(
            status="completed",
            content=str(output.get("content", "")),
            reasoning=str(output.get("reasoning", "")),
        )
