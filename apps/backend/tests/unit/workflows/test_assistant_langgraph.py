from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autoflow.providers.assistant.langgraph import (
    _CLIENT_ACTIONS,
    AssistantGraph,
    AssistantModelReply,
    AssistantToolCall,
)


def test_graph_exposes_approved_studio_action_families_only() -> None:
    assert {
        "load_workflow",
        "run_single_node",
        "clear_logs",
        "export_logs",
        "list_local_workflows",
        "save_workflow_to_folder",
        "list_scheduled_tasks_full",
        "create_scheduled_task",
        "get_global_config",
        "update_global_config",
        "open_global_config",
        "take_screenshot",
        "upload_image",
        "list_image_assets",
        "delete_image_asset",
        "rename_image_asset",
    } <= _CLIENT_ACTIONS
    assert {
        "upload_excel",
        "list_data_assets",
    }.isdisjoint(_CLIENT_ACTIONS)


class ScriptedModel:
    def __init__(self, *replies: AssistantModelReply) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    async def __call__(self, model_id: str, payload: dict[str, Any]) -> AssistantModelReply:
        self.requests.append({"modelId": model_id, **payload})
        return self.replies.pop(0)


@pytest.mark.asyncio
async def test_graph_waits_for_real_canvas_result_then_continues_model(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        AssistantModelReply(
            content="",
            reasoning="",
            tool_calls=(
                AssistantToolCall(
                    id="tool-1",
                    name="client_action",
                    arguments={
                        "action": "add_nodes",
                        "payload": {"nodes": [{"type": "open_page"}]},
                    },
                ),
            ),
        ),
        AssistantModelReply(content="节点已添加", reasoning="", tool_calls=()),
    )
    graph = AssistantGraph(tmp_path / "assistant-checkpoints.sqlite3", model)

    paused = await graph.start(
        thread_id="workspace/session-1",
        model_id="model-main",
        messages=[{"role": "user", "content": "添加打开网页节点"}],
        enable_tools=True,
    )

    assert paused.status == "waiting_for_action"
    assert paused.tool_call == AssistantToolCall(
        id="tool-1",
        name="client_action",
        arguments={
            "action": "add_nodes",
            "payload": {"nodes": [{"type": "open_page"}]},
        },
    )

    completed = await graph.resume(
        thread_id="workspace/session-1",
        command_id="tool-1",
        result={"success": True, "data": {"nodeIds": ["node-1"]}},
    )

    assert completed.status == "completed"
    assert completed.content == "节点已添加"
    assert len(model.requests) == 2
    assert model.requests[1]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "tool-1",
        "content": '{"data":{"nodeIds":["node-1"]},"success":true}',
    }


@pytest.mark.asyncio
async def test_graph_recreation_resumes_original_command_without_reissuing_action(
    tmp_path: Path,
) -> None:
    database = tmp_path / "assistant-checkpoints.sqlite3"
    first_model = ScriptedModel(
        AssistantModelReply(
            content="",
            reasoning="",
            tool_calls=(
                AssistantToolCall(
                    id="tool-2",
                    name="client_action",
                    arguments={"action": "rename_workflow", "payload": {"name": "采购"}},
                ),
            ),
        )
    )
    paused = await AssistantGraph(database, first_model).start(
        thread_id="workspace/session-2",
        model_id="model-main",
        messages=[{"role": "user", "content": "重命名"}],
        enable_tools=True,
    )
    assert paused.command_id == "tool-2"

    second_model = ScriptedModel(
        AssistantModelReply(content="已重命名", reasoning="", tool_calls=())
    )
    completed = await AssistantGraph(database, second_model).resume(
        thread_id="workspace/session-2",
        command_id="tool-2",
        result={"success": True},
    )

    assert completed.status == "completed"
    assert len(first_model.requests) == 1
    assert len(second_model.requests) == 1


@pytest.mark.asyncio
async def test_graph_rejects_excluded_node_before_frontend_side_effect(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        AssistantModelReply(
            content="",
            reasoning="",
            tool_calls=(
                AssistantToolCall(
                    id="tool-3",
                    name="client_action",
                    arguments={
                        "action": "add_nodes",
                        "payload": {"nodes": [{"type": "excel_write"}]},
                    },
                ),
            ),
        )
    )
    graph = AssistantGraph(tmp_path / "assistant-checkpoints.sqlite3", model)

    result = await graph.start(
        thread_id="workspace/session-3",
        model_id="model-main",
        messages=[{"role": "user", "content": "添加 Excel 节点"}],
        enable_tools=True,
    )

    assert result.status == "failed"
    assert result.error == "助手请求包含未批准的节点类型: excel_write"
    assert result.tool_call is None


@pytest.mark.asyncio
async def test_graph_rejects_stale_or_different_command_resume(tmp_path: Path) -> None:
    model = ScriptedModel(
        AssistantModelReply(
            content="",
            reasoning="",
            tool_calls=(
                AssistantToolCall(
                    id="tool-4",
                    name="client_action",
                    arguments={"action": "fit_view", "payload": {}},
                ),
            ),
        )
    )
    graph = AssistantGraph(tmp_path / "assistant-checkpoints.sqlite3", model)
    await graph.start(
        thread_id="workspace/session-4",
        model_id="model-main",
        messages=[{"role": "user", "content": "适应画布"}],
        enable_tools=True,
    )

    with pytest.raises(ValueError, match="工具命令身份不匹配"):
        await graph.resume(
            thread_id="workspace/session-4",
            command_id="different-command",
            result={"success": True},
        )
