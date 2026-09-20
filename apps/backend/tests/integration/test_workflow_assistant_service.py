from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.application.workflows.assistant import WorkflowAssistantService
from autoflow.domain.models import ModelError, ModelInvocationResult
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_assistant import (
    SqlAlchemyWorkflowAssistant,
)


class ScriptedModels:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(self, model_id: str, payload):
        self.calls += 1
        assert model_id == "model-main"
        if self.calls == 1:
            return ModelInvocationResult(
                "managed",
                "",
                "",
                {},
                "https://safe.test",
                (
                    {
                        "id": "tool-1",
                        "name": "client_action",
                        "arguments": {
                            "action": "add_nodes",
                            "payload": {"nodes": [{"type": "open_page"}]},
                        },
                    },
                ),
            )
        assert payload["messages"][-1]["role"] == "tool"
        assert payload["messages"][-1]["tool_call_id"] == "tool-1"
        assert payload["messages"][-1]["content"] in {
            '{"data":{"nodeIds":["node-1"]},"success":true}',
            '{"success":true}',
        }
        return ModelInvocationResult(
            "managed", "已添加打开网页节点", "", {}, "https://safe.test"
        )


class SlowModels:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def invoke(self, model_id: str, payload):
        self.started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class FallbackModels:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def invoke(self, model_id: str, payload):
        self.calls.append(model_id)
        if model_id == "model-primary":
            raise ModelError("MODEL_PROVIDER_RATE_LIMITED", "限流", 429)
        return ModelInvocationResult(
            model_id, "备用模型完成", "", {}, "https://safe.test"
        )


class StreamingModels:
    async def invoke(self, model_id: str, payload):
        on_chunk = payload["_onChunk"]
        await on_chunk("reasoning", "检查", "检查")
        await on_chunk("content", "已", "已")
        await on_chunk("content", "完成", "已完成")
        return ModelInvocationResult(
            model_id, "已完成", "检查", {}, "https://safe.test"
        )


class McpModels:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(self, model_id: str, payload):
        self.calls += 1
        names = [tool["function"]["name"] for tool in payload.get("tools", [])]
        assert "client_action" in names
        assert "mcp__fixture__echo" in names
        if self.calls == 1:
            return ModelInvocationResult(
                model_id,
                "",
                "",
                {},
                "https://safe.test",
                (
                    {
                        "id": "mcp-tool-1",
                        "name": "mcp__fixture__echo",
                        "arguments": {"text": "hello"},
                    },
                ),
            )
        assert "echo:hello" in payload["messages"][-1]["content"]
        return ModelInvocationResult(
            model_id, "MCP 已返回", "", {}, "https://safe.test"
        )


class UnknownMcpModels:
    async def invoke(self, model_id: str, payload):
        return ModelInvocationResult(
            model_id,
            "",
            "",
            {},
            "https://safe.test",
            (
                {
                    "id": "unknown-mcp-tool",
                    "name": "mcp__missing__tool",
                    "arguments": {},
                },
            ),
        )


class McpTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def tool_schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "mcp__fixture__echo",
                    "description": "echo",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                    },
                },
            }
        ]

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return {"content": f"echo:{arguments['text']}", "is_error": False}


class BlockingMcpTools(McpTools):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        self.started.set()
        await self.release.wait()
        return {"content": f"echo:{arguments['text']}", "is_error": False}


def _service(tmp_path: Path):
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    events = StudioEventJournal()
    models = ScriptedModels()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "workspace" / "assistant" / "checkpoints.sqlite3",
        models,
        events,
    )
    return service, events, factory, models


@pytest.mark.asyncio
async def test_mcp_tool_is_injected_and_runs_only_after_frontend_approval(
    tmp_path,
) -> None:
    database = tmp_path / "mcp-assistant.db"
    migrate_database(database)
    factory = create_session_factory(database)
    events = StudioEventJournal()
    models = McpModels()
    mcp = McpTools()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "mcp-checkpoints.sqlite3",
        models,
        events,
        mcp,
    )
    chat = asyncio.create_task(
        service.chat(
            session_id="mcp-session",
            message="调用 echo",
            model_id="model-main",
            enable_tools=True,
            workflow_context={},
        )
    )
    for _ in range(100):
        if events.sequence >= 3:
            break
        await asyncio.sleep(0.01)

    assert mcp.calls == []
    assert events.replay(after_sequence=2)[0].event == "ai_assistant:mcp_tool_request"
    await _claim(service, "mcp-session", "mcp-tool-1", "mcp-claim")
    receipt, status = await service.submit_event_command(
        "mcp-approve",
        "ai_client_action_ack",
        {
            "session_id": "mcp-session",
            "tool_call_id": "mcp-tool-1",
            "claim_command_id": "mcp-claim",
            "result": {"success": True},
        },
    )
    response = await asyncio.wait_for(chat, 2)

    assert status == 200 and receipt["success"] is True
    assert mcp.calls == [("mcp__fixture__echo", {"text": "hello"})]
    assert response["message"]["content"] == "MCP 已返回"
    factory.dispose()


@pytest.mark.asyncio
async def test_mcp_approval_retry_does_not_call_external_tool_twice(tmp_path) -> None:
    database = tmp_path / "mcp-retry.db"
    migrate_database(database)
    factory = create_session_factory(database)
    events = StudioEventJournal()
    mcp = BlockingMcpTools()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "mcp-retry-checkpoints.sqlite3",
        McpModels(),
        events,
        mcp,
    )
    chat = asyncio.create_task(
        service.chat(
            session_id="mcp-retry",
            message="调用 echo",
            model_id="model-main",
            enable_tools=True,
            workflow_context={},
        )
    )
    for _ in range(100):
        if events.sequence >= 3:
            break
        await asyncio.sleep(0.01)
    await _claim(service, "mcp-retry", "mcp-tool-1", "mcp-retry-claim")
    request = {
        "session_id": "mcp-retry",
        "tool_call_id": "mcp-tool-1",
        "claim_command_id": "mcp-retry-claim",
        "result": {"success": True},
    }
    first = asyncio.create_task(
        service.submit_event_command(
            "mcp-retry-result", "ai_client_action_ack", request
        )
    )
    await asyncio.wait_for(mcp.started.wait(), 1)
    repeated = asyncio.create_task(
        service.submit_event_command(
            "mcp-retry-result", "ai_client_action_ack", request
        )
    )
    await asyncio.sleep(0)
    assert mcp.calls == [("mcp__fixture__echo", {"text": "hello"})]
    mcp.release.set()

    assert await first == ({"commandId": "mcp-retry-result", "success": True}, 200)
    assert await repeated == ({"commandId": "mcp-retry-result", "success": True}, 200)
    assert (await asyncio.wait_for(chat, 2))["message"]["content"] == "MCP 已返回"
    assert len(mcp.calls) == 1
    factory.dispose()


@pytest.mark.asyncio
async def test_model_cannot_request_an_unregistered_mcp_tool(tmp_path) -> None:
    database = tmp_path / "mcp-missing.db"
    migrate_database(database)
    factory = create_session_factory(database)
    events = StudioEventJournal()
    mcp = McpTools()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "mcp-missing-checkpoints.sqlite3",
        UnknownMcpModels(),
        events,
        mcp,
    )

    response = await service.chat(
        session_id="mcp-missing",
        message="调用不存在的工具",
        model_id="model-main",
        enable_tools=True,
        workflow_context={},
    )

    assert (
        response["message"]["content"] == "MCP 工具未连接或不存在: mcp__missing__tool"
    )
    assert mcp.calls == []
    assert service.get_session("mcp-missing")["status"] == "failed"
    factory.dispose()


async def _claim(
    service: WorkflowAssistantService,
    session_id: str,
    tool_call_id: str,
    command_id: str,
) -> None:
    receipt, status = await service.submit_event_command(
        command_id,
        "ai_client_action_claim",
        {
            "session_id": session_id,
            "tool_call_id": tool_call_id,
            "executor_id": "test-window",
        },
    )
    assert status == 200 and receipt["success"] is True


@pytest.mark.asyncio
async def test_assistant_projects_tool_wait_and_result_to_numbered_events(
    tmp_path,
) -> None:
    service, events, factory, models = _service(tmp_path)
    chat = asyncio.create_task(
        service.chat(
            session_id="session-1",
            message="添加打开网页节点",
            model_id="model-main",
            enable_tools=True,
            workflow_context={"revision": 7, "nodes": []},
        )
    )
    for _ in range(100):
        if events.sequence >= 3:
            break
        await asyncio.sleep(0.01)

    projected = events.replay(after_sequence=0)
    assert [item.event for item in projected] == [
        "ai_assistant:assistant_partial",
        "ai_assistant:tool_call",
        "ai_assistant:client_action_request",
    ]
    request = projected[2].data
    assert request == {
        "session_id": "session-1",
        "tool_call_id": "tool-1",
        "action": "add_nodes",
        "payload": {"nodes": [{"type": "open_page"}]},
    }

    await _claim(service, "session-1", "tool-1", "claim-command-1")
    receipt, status = await service.submit_event_command(
        "command-1",
        "ai_client_action_ack",
        {
            "session_id": "session-1",
            "tool_call_id": "tool-1",
            "claim_command_id": "claim-command-1",
            "result": {"success": True, "data": {"nodeIds": ["node-1"]}},
        },
    )
    response = await asyncio.wait_for(chat, 2)

    assert status == 200 and receipt == {"commandId": "command-1", "success": True}
    assert response["message"]["content"] == "已添加打开网页节点"
    assert models.calls == 2
    assert [item.event for item in events.replay(after_sequence=3)] == [
        "ai_assistant:tool_result",
        "ai_assistant:content_partial",
    ]
    restored = service.get_session("session-1")
    assert restored["status"] == "completed"
    assert restored["pending_action"] is None
    assert restored["messages"][-1]["content"] == "已添加打开网页节点"
    factory.dispose()


@pytest.mark.asyncio
async def test_assistant_ack_is_idempotent_and_different_payload_conflicts(
    tmp_path,
) -> None:
    service, events, factory, _models = _service(tmp_path)
    chat = asyncio.create_task(
        service.chat(
            session_id="session-2",
            message="添加节点",
            model_id="model-main",
            enable_tools=True,
            workflow_context={},
        )
    )
    for _ in range(100):
        if events.sequence >= 3:
            break
        await asyncio.sleep(0.01)
    await _claim(service, "session-2", "tool-1", "claim-command-2")
    payload = {
        "session_id": "session-2",
        "tool_call_id": "tool-1",
        "claim_command_id": "claim-command-2",
        "result": {"success": True},
    }
    first = await service.submit_event_command(
        "command-2", "ai_client_action_ack", payload
    )
    assert (
        await service.submit_event_command("command-2", "ai_client_action_ack", payload)
        == first
    )
    conflict, status = await service.submit_event_command(
        "command-2",
        "ai_client_action_ack",
        {**payload, "result": {"success": False}},
    )
    assert status == 409 and conflict["success"] is False
    await chat
    factory.dispose()


@pytest.mark.asyncio
async def test_assistant_action_must_be_claimed_once_before_result(tmp_path) -> None:
    service, events, factory, _models = _service(tmp_path)
    chat = asyncio.create_task(
        service.chat(
            session_id="claimed-session",
            message="添加节点",
            model_id="model-main",
            enable_tools=True,
            workflow_context={},
        )
    )
    for _ in range(100):
        if events.sequence >= 3:
            break
        await asyncio.sleep(0.01)

    rejected, rejected_status = await service.submit_event_command(
        "result-before-claim",
        "ai_client_action_ack",
        {
            "session_id": "claimed-session",
            "tool_call_id": "tool-1",
            "claim_command_id": "claim-tool-1",
            "result": {"success": True},
        },
    )
    assert rejected_status == 409
    assert rejected["error"] == "工具请求尚未被认领"

    claim_payload = {
        "session_id": "claimed-session",
        "tool_call_id": "tool-1",
        "executor_id": "studio-window-1",
    }
    claimed = await service.submit_event_command(
        "claim-tool-1", "ai_client_action_claim", claim_payload
    )
    assert claimed == ({"commandId": "claim-tool-1", "success": True}, 200)
    assert (
        await service.submit_event_command(
            "claim-tool-1", "ai_client_action_claim", claim_payload
        )
        == claimed
    )

    conflict, conflict_status = await service.submit_event_command(
        "other-claim",
        "ai_client_action_claim",
        {**claim_payload, "executor_id": "studio-window-2"},
    )
    assert conflict_status == 409
    assert conflict["success"] is False

    receipt, status = await service.submit_event_command(
        "claimed-result",
        "ai_client_action_ack",
        {
            "session_id": "claimed-session",
            "tool_call_id": "tool-1",
            "claim_command_id": "claim-tool-1",
            "result": {"success": True},
        },
    )
    assert status == 200 and receipt["success"] is True
    await chat
    factory.dispose()


@pytest.mark.asyncio
async def test_cancel_interrupts_active_model_and_cannot_be_overwritten(
    tmp_path,
) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    models = SlowModels()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "workspace" / "assistant" / "checkpoints.sqlite3",
        models,
        StudioEventJournal(),
    )
    chat = asyncio.create_task(
        service.chat(
            session_id="cancel-session",
            message="生成流程",
            model_id="model-main",
            enable_tools=True,
            workflow_context={},
        )
    )
    await asyncio.wait_for(models.started.wait(), 1)

    assert await service.cancel("cancel-session") == {
        "success": True,
        "session_id": "cancel-session",
    }
    response = await asyncio.wait_for(chat, 1)

    assert models.cancelled.is_set()
    assert response["message"]["content"] == "[已停止] 任务被你打断。"
    restored = service.get_session("cancel-session")
    assert restored["status"] == "cancelled"
    assert restored["messages"][-1]["content"] == "[已停止] 任务被你打断。"
    factory.dispose()


@pytest.mark.asyncio
async def test_shutdown_interrupts_all_active_model_calls(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    models = SlowModels()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "workspace" / "assistant" / "checkpoints.sqlite3",
        models,
        StudioEventJournal(),
    )
    chat = asyncio.create_task(
        service.chat(
            session_id="shutdown-session",
            message="生成流程",
            model_id="model-main",
            enable_tools=True,
            workflow_context={},
        )
    )
    await asyncio.wait_for(models.started.wait(), 1)

    await service.shutdown()
    response = await asyncio.wait_for(chat, 1)

    assert models.cancelled.is_set()
    assert response["message"]["content"] == "[已停止] 服务正在关闭。"
    assert service.get_session("shutdown-session")["status"] == "cancelled"
    factory.dispose()


@pytest.mark.asyncio
async def test_assistant_uses_managed_fallback_ids_in_order(tmp_path) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    models = FallbackModels()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "workspace" / "assistant" / "checkpoints.sqlite3",
        models,
        StudioEventJournal(),
    )

    response = await service.chat(
        session_id="fallback-session",
        message="解释流程",
        model_id="model-primary",
        fallback_model_ids=["model-primary", "model-fallback"],
        enable_tools=False,
        workflow_context={},
    )

    assert models.calls == ["model-primary", "model-fallback"]
    assert response["message"]["content"] == "备用模型完成"
    factory.dispose()


@pytest.mark.asyncio
async def test_assistant_projects_real_model_chunks_to_numbered_events(
    tmp_path,
) -> None:
    database = tmp_path / "workspace.db"
    migrate_database(database)
    factory = create_session_factory(database)
    events = StudioEventJournal()
    service = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "workspace" / "assistant" / "checkpoints.sqlite3",
        StreamingModels(),
        events,
    )

    response = await service.chat(
        session_id="stream-session",
        message="检查流程",
        model_id="model-main",
        enable_tools=False,
        workflow_context={},
    )

    assert response["message"]["content"] == "已完成"
    projected = events.replay(after_sequence=0)
    assert [(item.sequence, item.event, item.data) for item in projected] == [
        (
            1,
            "ai_assistant:reasoning_partial",
            {
                "session_id": "stream-session",
                "delta": "检查",
                "full": "检查",
            },
        ),
        (
            2,
            "ai_assistant:content_partial",
            {"session_id": "stream-session", "delta": "已", "full": "已"},
        ),
        (
            3,
            "ai_assistant:content_partial",
            {
                "session_id": "stream-session",
                "delta": "完成",
                "full": "已完成",
            },
        ),
        (
            4,
            "ai_assistant:content_partial",
            {
                "session_id": "stream-session",
                "delta": "",
                "full": "已完成",
            },
        ),
    ]
    factory.dispose()


@pytest.mark.asyncio
async def test_confirmed_action_recovers_after_graph_advanced_before_session_save(
    tmp_path, monkeypatch
) -> None:
    service, events, factory, models = _service(tmp_path)
    chat = asyncio.create_task(
        service.chat(
            session_id="recover-session",
            message="添加节点",
            model_id="model-main",
            enable_tools=True,
            workflow_context={},
        )
    )
    for _ in range(100):
        if events.sequence >= 3:
            break
        await asyncio.sleep(0.01)

    async def crash_before_session_save(session_id, result):
        raise RuntimeError("simulated process loss")

    monkeypatch.setattr(service, "_apply_graph_result", crash_before_session_save)
    await _claim(service, "recover-session", "tool-1", "recover-claim")
    with pytest.raises(RuntimeError, match="simulated process loss"):
        await service.submit_event_command(
            "recover-command",
            "ai_client_action_ack",
            {
                "session_id": "recover-session",
                "tool_call_id": "tool-1",
                "claim_command_id": "recover-claim",
                "result": {"success": True},
            },
        )
    assert models.calls == 2

    restored = WorkflowAssistantService(
        SqlAlchemyWorkflowAssistant(factory),
        tmp_path / "workspace" / "assistant" / "checkpoints.sqlite3",
        models,
        StudioEventJournal(),
    )
    receipt, status = await restored.submit_event_command(
        "recover-command",
        "ai_client_action_ack",
        {
            "session_id": "recover-session",
            "tool_call_id": "tool-1",
            "claim_command_id": "recover-claim",
            "result": {"success": True},
        },
    )

    assert status == 200 and receipt["success"] is True
    assert models.calls == 2
    assert restored.get_session("recover-session")["status"] == "completed"
    chat.cancel()
    with pytest.raises(asyncio.CancelledError):
        await chat
    factory.dispose()
